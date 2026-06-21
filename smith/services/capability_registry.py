"""Declarative capabilities for deterministic assistant routing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from smith.services.intent_detection import is_context_detection_intent, is_follow_up

if TYPE_CHECKING:
    from smith.models.assistant import AssistantSession

EVIDENCE_PROJECT_STRUCTURE = "project_structure"
EVIDENCE_GIT_CHANGES = "git_changes"
EVIDENCE_FILE_CONTENTS = "file_contents"
EVIDENCE_PROJECT_CONTEXT = "project_context"
EVIDENCE_PLANNING_CONTEXT = "planning_context"
EVIDENCE_GIT_SUMMARY = "git_summary"
EVIDENCE_OPTIONAL_PROJECT_CONTEXT = "optional_project_context"

GENERAL_CHAT_ID = "general_chat"
DETECT_PROJECT_CONTEXT_ID = "detect_project_context"

_MULTI_WORD_WEIGHT = 3
_SINGLE_WORD_WEIGHT = 2
_SEMANTIC_MATCH_WEIGHT = 5


@dataclass(frozen=True, slots=True)
class Capability:
    id: str
    triggers: tuple[str, ...]
    required_evidence: tuple[str, ...]
    analytical: bool = True
    priority: int = 0
    semantic_match: bool = False

    def score(self, text: str) -> int:
        if self.semantic_match and is_context_detection_intent(text):
            return _SEMANTIC_MATCH_WEIGHT

        score = 0
        for trigger in self.triggers:
            if " " in trigger:
                if trigger in text:
                    score += _MULTI_WORD_WEIGHT
            elif re.search(rf"\b{re.escape(trigger)}\b", text):
                score += _SINGLE_WORD_WEIGHT
        return score


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

    text = message.lower().strip()
    best: Capability | None = None
    best_score = 0
    best_priority = -1

    for cap in _CAPABILITIES:
        if cap.id == GENERAL_CHAT_ID:
            continue
        score = cap.score(text)
        if score > best_score or (score == best_score and cap.priority > best_priority):
            best_score = score
            best_priority = cap.priority
            best = cap

    if best is not None and best_score > 0:
        return best
    return get_capability(GENERAL_CHAT_ID)


_CAPABILITIES: tuple[Capability, ...] = (
    Capability(
        DETECT_PROJECT_CONTEXT_ID,
        (
            "identify the context",
            "identify context",
            "identify project context",
            "detect project context",
            "detect context",
            "inspect context",
            "project context",
            "explain the context",
            "explain project context",
            "what kind of project",
            "what type of project",
            "what is this folder",
            "what is this directory",
            "identifique o contexto",
            "identificar o contexto",
            "identificar contexto",
            "detectar contexto",
            "detectar o contexto",
            "contexto da pasta",
            "contexto desta pasta",
            "contexto do projeto",
            "contexto deste projeto",
            "contexto do diretório",
            "contexto do diretorio",
            "que tipo de projeto",
            "qual tipo de projeto",
            "tipo de projeto",
            "inspect folder",
            "inspect directory",
            "inspect project type",
            "run context",
            "smith context",
            "through chat",
            "via chat",
        ),
        (EVIDENCE_PROJECT_CONTEXT,),
        analytical=False,
        priority=20,
        semantic_match=True,
    ),
    Capability(
        "explain_project",
        ("what is this project", "what is this repo", "what is this"),
        (EVIDENCE_PROJECT_STRUCTURE,),
        priority=5,
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
        priority=10,
    ),
    Capability(
        "review_architecture",
        ("review architecture", "architecture review", "architectural review", "architectural"),
        (EVIDENCE_PROJECT_STRUCTURE,),
        priority=15,
    ),
    Capability(
        "review_code",
        ("code review", "what changed", "changes"),
        (EVIDENCE_PROJECT_STRUCTURE, EVIDENCE_GIT_CHANGES),
        priority=12,
    ),
    Capability(
        "explain_file",
        ("explain file", "what does this file", "what is in this file", "what is in"),
        (EVIDENCE_FILE_CONTENTS, EVIDENCE_PROJECT_CONTEXT),
        priority=8,
    ),
    Capability(
        "compare_projects",
        ("compare", " vs ", "difference between", "versus"),
        (EVIDENCE_PROJECT_STRUCTURE,),
        priority=10,
    ),
    Capability(
        "plan_work",
        ("plan", "roadmap", "next steps", "how should i"),
        (EVIDENCE_PLANNING_CONTEXT,),
        priority=10,
    ),
    Capability(
        "summarize_repository",
        ("summarize repo", "repository overview", "tell me about this repo", "describe this repo"),
        (EVIDENCE_GIT_SUMMARY, EVIDENCE_PROJECT_STRUCTURE),
        priority=8,
    ),
    Capability(
        GENERAL_CHAT_ID,
        (),
        (EVIDENCE_OPTIONAL_PROJECT_CONTEXT,),
        analytical=False,
    ),
)
