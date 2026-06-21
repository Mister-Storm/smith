"""Map capabilities and user messages to evidence levels and investigation depth."""

from __future__ import annotations

from smith.models.assistant import (
    AnalysisRequirements,
    AssistantIntent,
    EvidenceLevel,
    InvestigationDepth,
)
from smith.services.capability_registry import Capability

MANDATORY_INVESTIGATION_INTENTS = frozenset(
    {
        AssistantIntent.ANALYZE_PROJECT,
        AssistantIntent.REVIEW_ARCHITECTURE,
        AssistantIntent.REVIEW_CODE,
        AssistantIntent.COMPARE_PROJECTS,
        AssistantIntent.SUMMARIZE_REPOSITORY,
    }
)

_DEEP_TRIGGERS = (
    "review architecture",
    "architecture review",
    "architectural review",
    "architectural",
)

_QUICK_TRIGGERS = (
    "what is this project",
    "what is this repo",
    "what is this",
    "summarize",
    "overview",
    "tell me about",
    "describe this repo",
)


def capability_to_intent(capability_id: str) -> AssistantIntent:
    mapping = {
        "explain_project": AssistantIntent.EXPLAIN_PROJECT,
        "analyze_project": AssistantIntent.ANALYZE_PROJECT,
        "review_architecture": AssistantIntent.REVIEW_ARCHITECTURE,
        "review_code": AssistantIntent.REVIEW_CODE,
        "compare_projects": AssistantIntent.COMPARE_PROJECTS,
        "summarize_repository": AssistantIntent.SUMMARIZE_REPOSITORY,
        "plan_work": AssistantIntent.PLAN_WORK,
        "explain_file": AssistantIntent.EXPLAIN_FILE,
        "general_chat": AssistantIntent.GENERAL_CHAT,
    }
    return mapping.get(capability_id, AssistantIntent.GENERAL_CHAT)


def resolve_depth(message: str, intent: AssistantIntent) -> InvestigationDepth:
    text = message.lower()
    if intent == AssistantIntent.REVIEW_ARCHITECTURE:
        return InvestigationDepth.DEEP
    if any(trigger in text for trigger in _DEEP_TRIGGERS):
        return InvestigationDepth.DEEP
    if intent == AssistantIntent.EXPLAIN_PROJECT:
        return InvestigationDepth.QUICK
    if intent == AssistantIntent.SUMMARIZE_REPOSITORY:
        return InvestigationDepth.STANDARD
    if any(trigger in text for trigger in _QUICK_TRIGGERS):
        if "improve" not in text and "analyze" not in text and "analysis" not in text:
            if "review" not in text:
                return InvestigationDepth.QUICK
    if intent in (AssistantIntent.ANALYZE_PROJECT, AssistantIntent.COMPARE_PROJECTS):
        return InvestigationDepth.STANDARD
    if "propose improvement" in text or "propose improvements" in text:
        return InvestigationDepth.STANDARD
    if "analyze" in text or "analysis" in text:
        return InvestigationDepth.STANDARD
    return InvestigationDepth.STANDARD


def required_levels_for_intent(
    intent: AssistantIntent,
    depth: InvestigationDepth,
) -> list[EvidenceLevel]:
    if intent == AssistantIntent.EXPLAIN_PROJECT:
        return [EvidenceLevel.STRUCTURE]
    if intent == AssistantIntent.SUMMARIZE_REPOSITORY:
        return [EvidenceLevel.STRUCTURE, EvidenceLevel.CONFIGURATION]
    if intent == AssistantIntent.REVIEW_ARCHITECTURE:
        return [
            EvidenceLevel.STRUCTURE,
            EvidenceLevel.CONFIGURATION,
            EvidenceLevel.SOURCE_CODE,
        ]
    if intent == AssistantIntent.ANALYZE_PROJECT:
        return [EvidenceLevel.STRUCTURE, EvidenceLevel.CONFIGURATION]
    if intent == AssistantIntent.COMPARE_PROJECTS:
        return [EvidenceLevel.STRUCTURE, EvidenceLevel.CONFIGURATION]
    if intent == AssistantIntent.REVIEW_CODE:
        return [EvidenceLevel.SOURCE_CODE]
    if intent == AssistantIntent.EXPLAIN_FILE:
        return [EvidenceLevel.SOURCE_CODE]
    return []


def build_requirements(capability: Capability, message: str) -> AnalysisRequirements:
    intent = capability_to_intent(capability.id)
    depth = resolve_depth(message, intent)
    levels = list(required_levels_for_intent(intent, depth))
    if intent == AssistantIntent.ANALYZE_PROJECT:
        text = message.lower()
        if any(trigger in text for trigger in ("improve", "suggest", "recommend", "melhoria", "melhorias", "proponha")):
            if EvidenceLevel.SOURCE_CODE not in levels:
                levels.append(EvidenceLevel.SOURCE_CODE)
    return AnalysisRequirements(intent=intent, required_levels=levels, depth=depth)


def is_mandatory_investigation_intent(intent: AssistantIntent) -> bool:
    return intent in MANDATORY_INVESTIGATION_INTENTS


def is_investigative_capability(capability_id: str) -> bool:
    intent = capability_to_intent(capability_id)
    if intent in MANDATORY_INVESTIGATION_INTENTS:
        return True
    return capability_id == "explain_project"
