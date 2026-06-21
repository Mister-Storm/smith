"""Declarative capabilities for deterministic assistant routing."""

from __future__ import annotations

import re

from smith.models.assistant import AssistantSession
from smith.services.intent_detection import is_follow_up

EVIDENCE_PROJECT_STRUCTURE = "project_structure"
EVIDENCE_GIT_CHANGES = "git_changes"
EVIDENCE_FILE_CONTENTS = "file_contents"
EVIDENCE_PROJECT_CONTEXT = "project_context"
EVIDENCE_PLANNING_CONTEXT = "planning_context"
EVIDENCE_GIT_SUMMARY = "git_summary"
EVIDENCE_OPTIONAL_PROJECT_CONTEXT = "optional_project_context"

GENERAL_CHAT_ID = "general_chat"


class Capability:
    __slots__ = ("id", "triggers", "required_evidence", "analytical")

    def __init__(
        self,
        id: str,
        triggers: tuple[str, ...],
        required_evidence: tuple[str, ...],
        *,
        analytical: bool = True,
    ) -> None:
        self.id = id
        self.triggers = triggers
        self.required_evidence = required_evidence
        self.analytical = analytical


def get_capability_registry() -> dict[str, Capability]:
    return {cap.id: cap for cap in _CAPABILITIES}


def get_capability(capability_id: str) -> Capability:
    registry = get_capability_registry()
    if capability_id not in registry:
        return registry[GENERAL_CHAT_ID]
    return registry[capability_id]


def match_capability(message: str, session: AssistantSession | None = None) -> Capability:
    if is_follow_up(message, session) and session and session.last_capability_id:
        return get_capability(session.last_capability_id)

    text = message.lower()
    best: Capability | None = None
    best_score = 0
    for cap in _CAPABILITIES:
        if cap.id == GENERAL_CHAT_ID:
            continue
        score = _score_capability(text, cap)
        if score > best_score:
            best_score = score
            best = cap
    if best is not None and best_score > 0:
        return best
    return get_capability_registry()[GENERAL_CHAT_ID]


def _score_capability(text: str, cap: Capability) -> int:
    score = 0
    for trigger in cap.triggers:
        if " " in trigger:
            if trigger in text:
                score += 3
        elif re.search(rf"\b{re.escape(trigger)}\b", text):
            score += 2
    return score


_CAPABILITIES: tuple[Capability, ...] = (
    Capability(
        "explain_project",
        ("what is this project", "what is this repo", "what is this"),
        (EVIDENCE_PROJECT_STRUCTURE,),
    ),
    Capability(
        "analyze_project",
        (
            "analyze",
            "analysis",
            "analise",
            "analisar",
            "architecture",
            "structure",
            "stack",
            "inspect project",
            "propose improvement",
            "propose improvements",
            "proponha melhorias",
            "proponha melhoria",
            "melhorias",
            "melhoria",
        ),
        (EVIDENCE_PROJECT_STRUCTURE,),
    ),
    Capability(
        "review_architecture",
        ("review architecture", "architecture review", "architectural review", "architectural"),
        (EVIDENCE_PROJECT_STRUCTURE,),
    ),
    Capability(
        "review_code",
        ("review", "code review", "what changed", "changes"),
        (EVIDENCE_PROJECT_STRUCTURE, EVIDENCE_GIT_CHANGES),
    ),
    Capability(
        "explain_file",
        ("explain", "what does", "what is in"),
        (EVIDENCE_FILE_CONTENTS, EVIDENCE_PROJECT_CONTEXT),
    ),
    Capability(
        "compare_projects",
        ("compare", " vs ", "difference between", "versus"),
        (EVIDENCE_PROJECT_STRUCTURE,),
    ),
    Capability(
        "plan_work",
        ("plan", "roadmap", "next steps", "how should i"),
        (EVIDENCE_PLANNING_CONTEXT,),
    ),
    Capability(
        "summarize_repository",
        ("summarize", "overview", "tell me about", "describe this repo"),
        (EVIDENCE_GIT_SUMMARY, EVIDENCE_PROJECT_STRUCTURE),
    ),
    Capability(
        GENERAL_CHAT_ID,
        (),
        (EVIDENCE_OPTIONAL_PROJECT_CONTEXT,),
        analytical=False,
    ),
)
