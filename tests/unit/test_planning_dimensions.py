from datetime import UTC, datetime

from smith.models.planning_context import PlanningContext, PlanningDimension
from smith.models.project_context import ProjectContext
from smith.models.user_context import UserContext
from smith.services.context_gap_analysis import detect_context_gaps


def _base_ctx(goal: str) -> PlanningContext:
    user = UserContext(
        interests=["team"],
        goals=["launch product"],
        primary_languages=["Python"],
        preferred_frameworks=[],
        working_domains=[],
        active_projects=[],
        recent_projects=[],
        generated_at=datetime.now(UTC),
        confidence=0.8,
        confidence_reason="",
        profile_completeness=80,
    )
    project = ProjectContext(
        project_name="app",
        language="python",
        framework="fastapi",
        build_system="poetry",
        database=[],
        infrastructure=[],
        ci_cd=["github-actions"],
        modules=["core"],
        generated_at=datetime.now(UTC),
    )
    return PlanningContext(user_context=user, project_context=project, goal=goal)


def _dims(goal: str) -> set[PlanningDimension]:
    ctx = _base_ctx(goal)
    gaps = detect_context_gaps(goal, ctx, knowns=[], constraints=[], assumptions=[])
    return {g.dimension for g in gaps if g.dimension is not None}


def test_success_criteria_satisfied_by_goal_keywords():
    assert PlanningDimension.SUCCESS_CRITERIA not in _dims(
        "build api with success metrics and measurable outcomes"
    )


def test_scope_satisfied_by_mvp_keyword():
    assert PlanningDimension.SCOPE not in _dims("deliver mvp for api")


def test_stakeholders_satisfied_by_audience_keyword():
    assert PlanningDimension.STAKEHOLDERS not in _dims("build tool for customer onboarding")


def test_timeline_satisfied_by_deadline_keyword():
    assert PlanningDimension.TIMELINE not in _dims("ship feature by end of month")


def test_risks_optional_gap_when_missing():
    dims = _dims("build api backend")
    assert PlanningDimension.RISKS in dims
