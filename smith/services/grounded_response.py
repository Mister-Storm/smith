"""Grounding guardrails and evidence-based response formatting."""

from __future__ import annotations

import logging
import re

from smith.core.exceptions import INVESTIGATION_FAILURE_MESSAGE, InvestigationFailure
from smith.models.assistant import (
    EvidenceBundle,
    EvidenceLevel,
    GroundedResponse,
    InvestigationReport,
    RepositoryKnowledge,
)
from smith.services.analysis_requirements import (
    MANDATORY_INVESTIGATION_INTENTS,
    build_requirements,
    capability_to_intent,
)
from smith.services.capability_registry import Capability
from smith.services.evidence_validator import is_cache_only, validate_requirements
from smith.services.investigation_trace import log_pre_llm

MIN_ANALYTICAL_CONFIDENCE = 0.45
logger = logging.getLogger(__name__)

_ANSWER_SYSTEM = (
    "You are Smith, a grounded repository investigator. Answer using ONLY the provided "
    "investigation findings and evidence. Do not invent files, modules, or project structure. "
    "Never ask the user to provide directory trees, build files, configuration, or source files "
    "that exist in the resolved repository. Provide actionable recommendations grounded in "
    "what was inspected on disk. Be concise and practical."
)

_DEFAULT_ATTEMPTS = (
    "structure inspection",
    "configuration inspection",
    "source code sampling",
)

_INTERNAL_TERM_REPLACEMENTS = (
    (re.compile(r"RepositoryKnowledge", re.I), "repository analysis"),
    (re.compile(r"ProjectKnowledge", re.I), "project analysis"),
    (re.compile(r"evidence cache", re.I), "cached hints"),
    (re.compile(r"project_context", re.I), "cached hints"),
    (re.compile(r"Only cached context collected", re.I), "Only cached hints available"),
)


def _sanitize_user_text(text: str) -> str:
    result = text
    for pattern, replacement in _INTERNAL_TERM_REPLACEMENTS:
        result = pattern.sub(replacement, result)
    return result


def should_generate_llm_response(
    capability: Capability,
    bundle: EvidenceBundle,
    *,
    missing: list[str] | None = None,
    knowledge: RepositoryKnowledge | None = None,
    message: str = "",
    investigation: InvestigationReport | None = None,
) -> tuple[bool, list[str]]:
    del knowledge  # optional cache only; never gates LLM invocation
    reasons: list[str] = [_sanitize_user_text(r) for r in (missing or [])]
    if capability.analytical:
        if reasons:
            return False, reasons
        requirements = build_requirements(capability, message)
        validation = validate_requirements(
            requirements,
            bundle,
            investigation_attempted=investigation.attempted if investigation else None,
            problems=investigation.problems if investigation else None,
        )
        if not validation.sufficient:
            reasons.extend(_sanitize_user_text(r) for r in validation.reasons)
        if is_cache_only(bundle) and capability_to_intent(capability.id) in (
            MANDATORY_INVESTIGATION_INTENTS
        ):
            reasons.append("Insufficient filesystem evidence — investigation incomplete")
        intent = capability_to_intent(capability.id)
        if intent in MANDATORY_INVESTIGATION_INTENTS and not _has_structure_evidence(bundle):
            reasons.append("No project structure evidence collected from disk")
        if (
            bundle.confidence.overall < MIN_ANALYTICAL_CONFIDENCE
            and intent in MANDATORY_INVESTIGATION_INTENTS
            and not _has_structure_evidence(bundle)
        ):
            reasons.append(f"Context confidence too low ({bundle.confidence.overall:.0%})")
        if capability.id == "compare_projects":
            structure_repos = _structure_repo_count(bundle)
            if structure_repos < 2:
                reasons.append("Need structure evidence for two resolved projects to compare")
        if capability.id == "explain_file" and not _has_source(bundle, "file"):
            reasons.append("No file contents collected")
    if reasons:
        return False, reasons
    return True, []


def generate_grounded_response(
    capability: Capability,
    bundle: EvidenceBundle,
    user_message: str,
    *,
    llm,
    history: list[tuple[str, str]] | None = None,
    missing: list[str] | None = None,
    knowledge: RepositoryKnowledge | None = None,
    investigation: InvestigationReport | None = None,
) -> GroundedResponse:
    allowed, block_reasons = should_generate_llm_response(
        capability,
        bundle,
        missing=missing,
        knowledge=knowledge,
        message=user_message,
        investigation=investigation,
    )
    if not allowed:
        return GroundedResponse(
            answer=format_blocked_response(
                block_reasons,
                bundle.confidence.overall,
                investigation=investigation,
            ),
            confidence=bundle.confidence.overall,
            blocked=True,
            missing=block_reasons,
            knowledge=knowledge,
        )

    if capability.id == "plan_work":
        return _planning_response(user_message, bundle)

    if capability.analytical and not bundle.items:
        raise InvestigationFailure(INVESTIGATION_FAILURE_MESSAGE)

    sections = _sections_from_knowledge(knowledge)
    prompt = _build_prompt(user_message, bundle, history or [], knowledge)
    log_pre_llm(bundle, knowledge)
    body = llm.generate(prompt, system=_ANSWER_SYSTEM)
    parsed = _extract_structured_sections(body)
    return GroundedResponse(
        answer=body,
        evidence=bundle.items,
        observations=sections.get("observations", []),
        recommendations=parsed.get("recommendations") or sections.get("recommendations", []),
        project_overview=parsed.get("project_overview") or sections.get("project_overview", []),
        architecture=parsed.get("architecture") or sections.get("architecture", []),
        strengths=parsed.get("strengths") or sections.get("strengths", []),
        risks=parsed.get("risks") or sections.get("risks", []),
        confidence=bundle.confidence.overall,
        blocked=False,
        knowledge=knowledge,
    )


def format_grounded_response(response: GroundedResponse) -> str:
    if response.blocked:
        return response.answer
    lines: list[str] = []
    if response.answer.strip():
        lines.append(response.answer.rstrip())
        lines.append("")

    if response.project_overview or (response.knowledge and response.knowledge.technologies):
        lines.append("Project Overview")
        for item in response.project_overview or _overview_from_knowledge(response.knowledge):
            lines.append(f"- {item}")
        lines.append("")

    if response.architecture or (response.knowledge and response.knowledge.architectural_patterns):
        lines.append("Architecture")
        for item in response.architecture or _architecture_from_knowledge(response.knowledge):
            lines.append(f"- {item}")
        lines.append("")

    if response.strengths:
        lines.append("Strengths")
        for item in response.strengths[:8]:
            lines.append(f"- {item}")
        lines.append("")

    if response.risks or (response.knowledge and response.knowledge.risks):
        lines.append("Risks")
        for item in response.risks or (response.knowledge.risks if response.knowledge else []):
            lines.append(f"- {item}")
        lines.append("")

    if response.recommendations:
        lines.append("Recommendations")
        for rec in response.recommendations[:8]:
            lines.append(f"- {rec}")
        lines.append("")

    if response.evidence:
        lines.append("Evidence")
        for item in response.evidence[:8]:
            if (item.metadata or {}).get("evidence_level") != EvidenceLevel.CACHE.value:
                lines.append(f"- {item.summary} ({item.source})")
        lines.append("")

    lines.append(f"Context confidence: {response.confidence:.0%}")
    return "\n".join(lines).rstrip()


def format_blocked_response(
    reasons: list[str],
    confidence: float,
    *,
    investigation: InvestigationReport | None = None,
) -> str:
    attempted = list(investigation.attempted) if investigation and investigation.attempted else []
    if not attempted:
        attempted = list(_DEFAULT_ATTEMPTS)
    problems = list(investigation.problems) if investigation and investigation.problems else []
    if not problems:
        problems = [_sanitize_user_text(r) for r in reasons if r]
    else:
        problems = [_sanitize_user_text(p) for p in problems]

    lines = [
        "I could not inspect the repository contents.",
        "",
        "Investigation attempted:",
    ]
    lines.extend(f"- {step}" for step in attempted)
    lines.extend(["", "Problems encountered:"])
    lines.extend(f"- {problem}" for problem in problems[:8])
    lines.extend(
        [
            "",
            f"Context confidence: {confidence:.0%}",
            "",
            "Suggested actions:",
            "- verify the repository path is correct",
            "- check read permissions on the repository directory",
        ]
    )
    return "\n".join(lines)


def answer_from_knowledge(
    user_message: str,
    knowledge: RepositoryKnowledge,
) -> GroundedResponse | None:
    text = user_message.lower()
    if "framework" in text or "stack" in text or "technology" in text:
        items = knowledge.frameworks or knowledge.technologies
        answer = ", ".join(items) if items else "No frameworks detected from investigation."
        return GroundedResponse(
            answer=answer,
            project_overview=_overview_from_knowledge(knowledge),
            architecture=_architecture_from_knowledge(knowledge),
            strengths=knowledge.strengths,
            risks=knowledge.risks,
            recommendations=[],
            confidence=0.85,
            knowledge=knowledge,
        )
    if "test" in text:
        answer = "\n".join(f"- {s}" for s in knowledge.testing_signals) or "No test signals found."
        return GroundedResponse(
            answer=f"Test organization signals:\n{answer}",
            strengths=knowledge.strengths,
            risks=knowledge.risks,
            confidence=0.85,
            knowledge=knowledge,
        )
    if "risk" in text or "concern" in text or "problem" in text:
        answer = "\n".join(f"- {r}" for r in knowledge.risks) or "No major risks detected."
        return GroundedResponse(
            answer=f"Biggest risks:\n{answer}",
            risks=knowledge.risks,
            strengths=knowledge.strengths,
            confidence=0.85,
            knowledge=knowledge,
        )
    return None


def _sections_from_knowledge(knowledge: RepositoryKnowledge | None) -> dict[str, list[str]]:
    if knowledge is None:
        return {}
    return {
        "project_overview": _overview_from_knowledge(knowledge),
        "architecture": _architecture_from_knowledge(knowledge),
        "strengths": knowledge.strengths,
        "risks": knowledge.risks,
        "recommendations": [],
        "observations": knowledge.observations,
    }


def _overview_from_knowledge(knowledge: RepositoryKnowledge | None) -> list[str]:
    if knowledge is None:
        return []
    lines: list[str] = []
    if knowledge.technologies:
        lines.append(f"Technologies: {', '.join(knowledge.technologies)}")
    if knowledge.frameworks:
        lines.append(f"Frameworks: {', '.join(knowledge.frameworks)}")
    if knowledge.modules:
        lines.append(f"Modules: {', '.join(knowledge.modules[:8])}")
    for obs in knowledge.observations[:3]:
        if obs not in lines:
            lines.append(obs)
    return lines


def _architecture_from_knowledge(knowledge: RepositoryKnowledge | None) -> list[str]:
    if knowledge is None:
        return []
    lines = list(knowledge.architectural_patterns)
    for signal in knowledge.deployment_signals[:2]:
        lines.append(signal)
    return lines


def _build_prompt(
    user_message: str,
    bundle: EvidenceBundle,
    history: list[tuple[str, str]],
    knowledge: RepositoryKnowledge | None,
) -> str:
    lines = ["Repository investigation findings:", ""]

    for item in bundle.items:
        if (item.metadata or {}).get("evidence_level") == EvidenceLevel.CACHE.value:
            continue
        level = (item.metadata or {}).get("evidence_level", "evidence")
        lines.append(f"- [{level}] {item.summary}")
        if item.detail and len(item.detail) < 1200:
            lines.append(f"  {item.detail[:800]}")
    lines.append("")

    if knowledge and knowledge.is_substantive():
        lines.append("Detected summary:")
        if knowledge.technologies:
            lines.append(f"Technologies: {', '.join(knowledge.technologies)}")
        if knowledge.frameworks:
            lines.append(f"Frameworks: {', '.join(knowledge.frameworks)}")
        if knowledge.modules:
            lines.append(f"Modules: {', '.join(knowledge.modules)}")
        if knowledge.architectural_patterns:
            lines.append(f"Architecture patterns: {', '.join(knowledge.architectural_patterns)}")
        if knowledge.strengths:
            lines.append(f"Strengths: {'; '.join(knowledge.strengths)}")
        if knowledge.risks:
            lines.append(f"Risks: {'; '.join(knowledge.risks)}")
        if knowledge.testing_signals:
            lines.append(f"Testing: {'; '.join(knowledge.testing_signals)}")
        if knowledge.observations:
            lines.append(f"Observations: {'; '.join(knowledge.observations)}")
        lines.append("")

    if history:
        lines.append("Recent conversation:")
        for role, content in history[-6:]:
            label = "User" if role == "user" else "Assistant"
            lines.append(f"{label}: {content[:500]}")
        lines.append("")

    lines.append(f"User question: {user_message}")
    lines.append(
        "Answer using the investigation findings above. "
        "Structure your answer with sections: Project Overview, Architecture, "
        "Strengths, Risks, Recommendations. Do not ask for files on disk."
    )
    return "\n".join(lines)


def _planning_response(user_message: str, bundle: EvidenceBundle) -> GroundedResponse:
    planning_item = next((i for i in bundle.items if i.source == "planning"), None)
    detail = planning_item.detail if planning_item else "Planning context unavailable."
    meta = planning_item.metadata if planning_item else {}
    confidence = float(meta.get("confidence", bundle.confidence.overall))
    gap_count = int(meta.get("gap_count", 0))
    blocked = gap_count > 0 or confidence < MIN_ANALYTICAL_CONFIDENCE
    if blocked:
        return GroundedResponse(
            answer=format_blocked_response(
                ["Planning requires more context — run /plan or answer clarification questions"],
                confidence,
            ),
            evidence=bundle.items,
            confidence=confidence,
            blocked=True,
            missing=["Planning gaps remain"],
        )
    return GroundedResponse(
        answer=detail,
        evidence=bundle.items,
        observations=["Planning context assembled from cached sources"],
        recommendations=["Run /plan with your goal when ready to generate a plan"],
        confidence=confidence,
        blocked=False,
    )


def _has_filesystem_level(bundle: EvidenceBundle, level: EvidenceLevel) -> bool:
    for item in bundle.items:
        if item.source != "filesystem":
            continue
        meta = item.metadata or {}
        if meta.get("evidence_level") == level.value:
            return True
    return False


def _has_structure_evidence(bundle: EvidenceBundle) -> bool:
    return _has_filesystem_level(bundle, EvidenceLevel.STRUCTURE)


def _structure_repo_count(bundle: EvidenceBundle) -> int:
    repos: set[str] = set()
    for item in bundle.items:
        if item.source != "filesystem":
            continue
        meta = item.metadata or {}
        if meta.get("evidence_level") != EvidenceLevel.STRUCTURE.value:
            continue
        if item.path:
            repos.add(item.path)
    return len(repos)


def _has_source(bundle: EvidenceBundle, source: str) -> bool:
    return any(item.source == source for item in bundle.items)


def _extract_structured_sections(body: str) -> dict[str, list[str]]:
    mapping = {
        "project overview": "project_overview",
        "architecture": "architecture",
        "strengths": "strengths",
        "risks": "risks",
        "recommendations": "recommendations",
        "observations": "observations",
    }
    result: dict[str, list[str]] = {key: [] for key in mapping.values()}
    section: str | None = None
    for line in body.splitlines():
        lower = line.strip().lower().rstrip(":")
        if lower in mapping:
            section = mapping[lower]
            continue
        if line.strip().startswith("#"):
            header = line.strip().lstrip("#").strip().lower()
            section = mapping.get(header)
            continue
        text = line.strip().lstrip("-•* ").strip()
        if not text or section is None:
            continue
        result[section].append(text)
    return result
