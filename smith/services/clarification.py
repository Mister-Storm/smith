"""Convert context gaps into actionable clarification questions."""

from __future__ import annotations

import re

from smith.models.planning_context import (
    ClarificationQuestion,
    ContextGap,
    GapSeverity,
    PlanningDimension,
)
from smith.services.context_gap_analysis import structural_gaps

MAX_QUESTIONS = 5

DIMENSION_QUESTION_MAP: dict[PlanningDimension, tuple[str, str]] = {
    PlanningDimension.OBJECTIVE: (
        "Can you clarify the primary objective?",
        "A clear objective anchors the plan.",
    ),
    PlanningDimension.SUCCESS_CRITERIA: (
        "What would make this effort successful?",
        "Success criteria guide planning decisions.",
    ),
    PlanningDimension.SCOPE: (
        "What is in scope and explicitly out of scope?",
        "Scope boundaries reduce ambiguity.",
    ),
    PlanningDimension.CONSTRAINTS: (
        "What constraints must the plan respect?",
        "Constraints limit viable approaches.",
    ),
    PlanningDimension.STAKEHOLDERS: (
        "Who will use or benefit from this outcome?",
        "Stakeholders influence requirements and priorities.",
    ),
    PlanningDimension.TIMELINE: (
        "What timeline or deadline should be considered?",
        "Timeline affects prioritization and scope.",
    ),
    PlanningDimension.RESOURCES: (
        "What resources are already available?",
        "Available resources constrain implementation choices.",
    ),
    PlanningDimension.RISKS: (
        "What major risks or concerns should be considered?",
        "Risks influence mitigation strategies.",
    ),
}

STRUCTURAL_QUESTION_MAP: dict[str, tuple[str, str]] = {
    "Project Context": (
        "Should planning use the current repository context?",
        "Run `smith refresh-context .` to ground plans in this project.",
    ),
    "Workspace Context": (
        "Should planning consider your broader workspace?",
        "Run `smith workspace .` to include multi-project context.",
    ),
    "User Profile Goals": (
        "What personal goals should this plan align with?",
        "Run `smith profile set-goal <goal>` to align planning with your priorities.",
    ),
}


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


def _severity_rank(gap: ContextGap) -> int:
    if gap.dimension is None:
        return 0
    order = {
        GapSeverity.CRITICAL: 1,
        GapSeverity.IMPORTANT: 2,
        GapSeverity.OPTIONAL: 3,
    }
    return order.get(gap.severity, 4)


def generate_questions_from_gaps(
    gaps: list[ContextGap],
    *,
    max_questions: int = MAX_QUESTIONS,
) -> list[ClarificationQuestion]:
    ranked = sorted(gaps, key=_severity_rank)
    questions: list[ClarificationQuestion] = []
    seen: set[str] = set()

    for gap in ranked:
        if gap.dimension is None:
            question, reason = STRUCTURAL_QUESTION_MAP.get(
                gap.name,
                (f"Can you resolve: {gap.name}?", gap.reason),
            )
            gap_id = _slug(gap.name)
        else:
            question, reason = DIMENSION_QUESTION_MAP[gap.dimension]
            gap_id = gap.dimension.value

        if gap_id in seen:
            continue
        seen.add(gap_id)
        questions.append(
            ClarificationQuestion(
                id=gap_id,
                question=question,
                reason=reason,
            )
        )
        if len(questions) >= max_questions:
            break

    return questions


def generate_questions(
    gaps: list[ContextGap],
    goal: str,
    *,
    max_questions: int = MAX_QUESTIONS,
) -> list[ClarificationQuestion]:
    del goal
    return generate_questions_from_gaps(gaps, max_questions=max_questions)


def has_blocking_gaps(gaps: list[ContextGap]) -> bool:
    if structural_gaps(gaps):
        return True
    return any(
        g.severity in (GapSeverity.CRITICAL, GapSeverity.IMPORTANT)
        for g in gaps
        if g.dimension is not None
    )
