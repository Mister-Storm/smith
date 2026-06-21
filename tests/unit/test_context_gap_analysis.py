from datetime import UTC, datetime

from smith.models.planning_context import (
    GapSeverity,
    PlanningContext,
    PlanningDecision,
    PlanningDimension,
)
from smith.models.project_context import ProjectContext
from smith.models.user_context import UserContext
from smith.services.context_gap_analysis import (
    apply_decisions,
    detect_context_gaps,
    structural_gaps,
)


def _user(*, goals: list[str] | None = None) -> UserContext:
    return UserContext(
        interests=["developers"],
        goals=goals or ["ship mvp"],
        primary_languages=["Python"],
        preferred_frameworks=["FastAPI"],
        working_domains=["Software"],
        active_projects=["app"],
        recent_projects=[],
        generated_at=datetime.now(UTC),
        confidence=0.8,
        confidence_reason="",
        profile_completeness=80,
    )


def _project() -> ProjectContext:
    return ProjectContext(
        project_name="app",
        language="python",
        framework="fastapi",
        build_system="poetry",
        database=[],
        infrastructure=[],
        ci_cd=[],
        modules=["api"],
        generated_at=datetime.now(UTC),
    )


def _ctx(*, project=None, workspace=None, goal="build api by end of quarter for users"):
    user = _user()
    ctx = PlanningContext(
        user_context=user,
        project_context=project,
        workspace_context=workspace,
        goal=goal,
    )
    return ctx


def test_structural_gaps_when_caches_missing():
    ctx = _ctx(project=None, workspace=None)
    gaps = detect_context_gaps(ctx.goal or "", ctx, knowns=[], constraints=[], assumptions=[])
    structural = structural_gaps(gaps)
    names = {g.name for g in structural}
    assert "Project Context" in names
    assert "Workspace Context" in names


def test_dimension_gap_includes_reason_citations():
    ctx = _ctx(project=_project())
    gaps = detect_context_gaps(
        "build api",
        ctx,
        knowns=[],
        constraints=[],
        assumptions=[],
    )
    timeline = next(g for g in gaps if g.dimension == PlanningDimension.TIMELINE)
    assert "goal statement" in timeline.reason


def test_apply_decisions_removes_answered_dimensions():
    ctx = _ctx(project=_project())
    gaps = detect_context_gaps(ctx.goal or "", ctx, knowns=[], constraints=[], assumptions=[])
    decisions = [
        PlanningDecision(
            dimension=PlanningDimension.TIMELINE,
            answer="3 months",
            recorded_at="2026-01-01T00:00:00Z",
        )
    ]
    filtered = apply_decisions(gaps, decisions)
    assert all(g.dimension != PlanningDimension.TIMELINE for g in filtered)


def test_empty_goal_emits_objective_gap():
    ctx = _ctx(project=_project(), goal="")
    gaps = detect_context_gaps("", ctx, knowns=[], constraints=[], assumptions=[])
    assert any(g.dimension == PlanningDimension.OBJECTIVE for g in gaps)
    objective = next(g for g in gaps if g.dimension == PlanningDimension.OBJECTIVE)
    assert objective.severity == GapSeverity.CRITICAL
