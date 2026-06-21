"""Deterministic context gap analysis for guided planning."""

from __future__ import annotations

import re

from smith.models.planning_context import (
    ContextGap,
    GapSeverity,
    PlanningConstraint,
    PlanningContext,
    PlanningDecision,
    PlanningDimension,
    PlanningKnown,
)

DIMENSION_LABELS: dict[PlanningDimension, str] = {
    PlanningDimension.OBJECTIVE: "Objective",
    PlanningDimension.SUCCESS_CRITERIA: "Success Criteria",
    PlanningDimension.SCOPE: "Scope",
    PlanningDimension.CONSTRAINTS: "Constraints",
    PlanningDimension.STAKEHOLDERS: "Stakeholders",
    PlanningDimension.TIMELINE: "Timeline",
    PlanningDimension.RESOURCES: "Resources",
    PlanningDimension.RISKS: "Risks",
}

SUCCESS_KEYWORDS = ("success", "metric", "measure", "outcome", "kpi", "goal", "target")
SCOPE_KEYWORDS = ("scope", "boundary", "boundaries", "mvp", "phase", "out of scope")
STAKEHOLDER_KEYWORDS = (
    "user",
    "users",
    "audience",
    "customer",
    "customers",
    "reader",
    "readers",
    "student",
    "students",
    "team",
    "beneficiary",
)
TIMELINE_KEYWORDS = (
    "deadline",
    "timeline",
    "quarter",
    "week",
    "month",
    "year",
    "by ",
    "due",
    "schedule",
)
RISK_KEYWORDS = ("risk", "concern", "mitigation", "blocker", "dependency")


def structural_gaps(gaps: list[ContextGap]) -> list[ContextGap]:
    return [g for g in gaps if g.dimension is None]


def critical_dimension_gaps(gaps: list[ContextGap]) -> list[ContextGap]:
    return [g for g in gaps if g.dimension is not None and g.severity == GapSeverity.CRITICAL]


def important_dimension_gaps(gaps: list[ContextGap]) -> list[ContextGap]:
    return [g for g in gaps if g.dimension is not None and g.severity == GapSeverity.IMPORTANT]


def gaps_by_severity(gaps: list[ContextGap], severity: GapSeverity) -> list[ContextGap]:
    return [g for g in gaps if g.severity == severity]


def apply_decisions(
    gaps: list[ContextGap],
    decisions: list[PlanningDecision],
) -> list[ContextGap]:
    answered = {d.dimension for d in decisions}
    return [g for g in gaps if g.dimension is None or g.dimension not in answered]


def detect_context_gaps(
    goal: str,
    ctx: PlanningContext,
    *,
    knowns: list[PlanningKnown],
    constraints: list[PlanningConstraint],
    assumptions: list[str],
) -> list[ContextGap]:
    del assumptions
    gaps: list[ContextGap] = []
    goal_lower = goal.lower().strip()

    if ctx.project_context is None:
        gaps.append(
            ContextGap(
                name="Project Context",
                dimension=None,
                reason=(
                    "No project context found in:\n"
                    "- project context cache\n"
                    "Run `smith refresh-context .` to ground plans in this project."
                ),
                severity=GapSeverity.CRITICAL,
                source="Structural Context",
            )
        )
    if ctx.workspace_context is None:
        gaps.append(
            ContextGap(
                name="Workspace Context",
                dimension=None,
                reason=(
                    "No workspace summary found in:\n"
                    "- workspace context cache\n"
                    "Run `smith workspace .` to include multi-project context."
                ),
                severity=GapSeverity.CRITICAL,
                source="Structural Context",
            )
        )
    if not ctx.user_context.goals:
        gaps.append(
            ContextGap(
                name="User Profile Goals",
                dimension=None,
                reason=(
                    "No user goals found in:\n"
                    "- user context\n"
                    "Run `smith profile set-goal <goal>` to align planning with your priorities."
                ),
                severity=GapSeverity.CRITICAL,
                source="Structural Context",
            )
        )

    if not goal_lower:
        gaps.append(
            _dimension_gap(
                PlanningDimension.OBJECTIVE,
                GapSeverity.CRITICAL,
                "No goal statement provided.",
            )
        )
    else:
        gaps.extend(_evaluate_dimensions(goal_lower, ctx, knowns, constraints))

    return gaps


def _dimension_gap(
    dimension: PlanningDimension,
    severity: GapSeverity,
    reason: str,
) -> ContextGap:
    return ContextGap(
        name=DIMENSION_LABELS[dimension],
        dimension=dimension,
        reason=reason,
        severity=severity,
        source="Gap Analysis",
    )


def _goal_has_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(kw in text for kw in keywords)


def _evaluate_dimensions(
    goal_lower: str,
    ctx: PlanningContext,
    knowns: list[PlanningKnown],
    constraints: list[PlanningConstraint],
) -> list[ContextGap]:
    gaps: list[ContextGap] = []
    user = ctx.user_context
    project = ctx.project_context

    if not _goal_has_any(goal_lower, SUCCESS_KEYWORDS) and not user.goals:
        gaps.append(
            _dimension_gap(
                PlanningDimension.SUCCESS_CRITERIA,
                GapSeverity.CRITICAL,
                _reason_missing(
                    "No measurable success indicators detected",
                    ["goal statement", "user context goals"],
                ),
            )
        )

    has_scope = _goal_has_any(goal_lower, SCOPE_KEYWORDS) or (
        project is not None and bool(project.modules)
    )
    if not has_scope:
        gaps.append(
            _dimension_gap(
                PlanningDimension.SCOPE,
                GapSeverity.IMPORTANT,
                _reason_missing(
                    "No scope boundaries detected",
                    ["goal statement", "project modules"],
                ),
            )
        )

    if not constraints:
        gaps.append(
            _dimension_gap(
                PlanningDimension.CONSTRAINTS,
                GapSeverity.IMPORTANT,
                _reason_missing(
                    "No explicit constraints detected",
                    ["project context", "git context", "user goals"],
                ),
            )
        )

    has_stakeholders = bool(user.interests) or _goal_has_any(goal_lower, STAKEHOLDER_KEYWORDS)
    if not has_stakeholders:
        gaps.append(
            _dimension_gap(
                PlanningDimension.STAKEHOLDERS,
                GapSeverity.IMPORTANT,
                _reason_missing(
                    "No stakeholder or audience information detected",
                    ["goal statement", "user interests"],
                ),
            )
        )

    if not _goal_has_any(goal_lower, TIMELINE_KEYWORDS):
        gaps.append(
            _dimension_gap(
                PlanningDimension.TIMELINE,
                GapSeverity.CRITICAL,
                _reason_missing(
                    "No timeline information found",
                    ["goal statement", "user context", "project context"],
                ),
            )
        )

    has_resources = bool(knowns) and any(
        k.source in ("Project Context", "Workspace Context", "User Context") for k in knowns
    )
    if not has_resources:
        gaps.append(
            _dimension_gap(
                PlanningDimension.RESOURCES,
                GapSeverity.OPTIONAL,
                _reason_missing(
                    "Limited resource signals detected",
                    ["project context", "workspace context", "user context"],
                ),
            )
        )

    if not _goal_has_any(goal_lower, RISK_KEYWORDS):
        gaps.append(
            _dimension_gap(
                PlanningDimension.RISKS,
                GapSeverity.OPTIONAL,
                _reason_missing(
                    "No risks or concerns mentioned",
                    ["goal statement"],
                ),
            )
        )

    return gaps


def _reason_missing(summary: str, sources: list[str]) -> str:
    lines = [f"{summary} in:"]
    lines.extend(f"- {source}" for source in sources)
    return "\n".join(lines)


def gap_dimension_ids(gaps: list[ContextGap]) -> list[str]:
    return [g.dimension.value for g in gaps if g.dimension is not None]


def validate_gap_order(
    original: list[ContextGap],
    reordered: list[ContextGap],
) -> bool:
    orig_dims = [g.dimension for g in original if g.dimension is not None]
    new_dims = [g.dimension for g in reordered if g.dimension is not None]
    return (
        orig_dims == new_dims
        or sorted(orig_dims, key=lambda d: d.value) == sorted(new_dims, key=lambda d: d.value)
        and len(orig_dims) == len(new_dims)
        and set(orig_dims) == set(new_dims)
    )


def parse_dimension_slug(value: str) -> PlanningDimension | None:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    for dim in PlanningDimension:
        if dim.value == normalized or dim.name.lower() == normalized:
            return dim
    aliases = {
        "success": PlanningDimension.SUCCESS_CRITERIA,
        "criteria": PlanningDimension.SUCCESS_CRITERIA,
        "stakeholder": PlanningDimension.STAKEHOLDERS,
        "resource": PlanningDimension.RESOURCES,
        "risk": PlanningDimension.RISKS,
        "constraint": PlanningDimension.CONSTRAINTS,
    }
    return aliases.get(normalized)
