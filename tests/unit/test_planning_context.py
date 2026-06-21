from datetime import UTC, datetime

from smith.models.planning_context import (
    ClarificationQuestion,
    ContextGap,
    GapSeverity,
    PlanningConstraint,
    PlanningContext,
    PlanningDecision,
    PlanningDimension,
    PlanningKnown,
    PlanningReadiness,
    PlanningResult,
)


def test_planning_known_defaults():
    known = PlanningKnown(text="Uses Docker", source="Project Context")
    assert known.evidence == []


def test_planning_context_fields():
    from smith.models.user_context import UserContext

    user = UserContext(
        interests=[],
        goals=[],
        primary_languages=["Python"],
        preferred_frameworks=[],
        working_domains=[],
        active_projects=[],
        recent_projects=[],
        generated_at=datetime.now(UTC),
        confidence=0.5,
        confidence_reason="",
        profile_completeness=20,
    )
    ctx = PlanningContext(user_context=user, goal="build api")
    assert ctx.knowns == []
    assert ctx.gaps == []
    assert ctx.decisions == []


def test_context_gap_model():
    gap = ContextGap(
        name="Timeline",
        dimension=PlanningDimension.TIMELINE,
        reason="No timeline found",
        severity=GapSeverity.CRITICAL,
        source="Gap Analysis",
    )
    assert gap.dimension == PlanningDimension.TIMELINE


def test_planning_result_and_readiness():
    gap = ContextGap(
        name="Timeline",
        dimension=PlanningDimension.TIMELINE,
        reason="missing",
        severity=GapSeverity.CRITICAL,
        source="Gap Analysis",
    )
    result = PlanningResult(
        goal="build api",
        knowns=[],
        gaps=[gap],
        assumptions=[],
        constraints=[],
        decisions=[],
        questions=[ClarificationQuestion(id="timeline", question="When?", reason="Scope")],
        plan=None,
        confidence=0.4,
        planning_mode="clarification_required",
    )
    assert result.plan is None
    readiness = PlanningReadiness(
        known_count=3,
        gap_count=2,
        critical_gap_count=1,
        important_gap_count=1,
        assumption_count=1,
        constraint_count=1,
        context_quality=0.6,
        confidence=0.55,
        status="Clarification Required",
    )
    assert readiness.gap_count == 2


def test_planning_decision():
    decision = PlanningDecision(
        dimension=PlanningDimension.TIMELINE,
        answer="3 months",
        recorded_at="2026-01-01T00:00:00Z",
    )
    assert decision.answer == "3 months"


def test_planning_constraint():
    constraint = PlanningConstraint(text="Use existing CI", source="Project Context")
    assert constraint.source == "Project Context"
