from datetime import UTC, datetime

from typer.testing import CliRunner

from smith.cli.app import app
from smith.models.planning_context import PlanningDimension
from smith.models.project_context import ProjectContext
from smith.models.user_context import UserContext
from smith.services.planner import PlanningService, set_last_planning_result

runner = CliRunner()


def _rich_user() -> UserContext:
    return UserContext(
        interests=["drones"],
        goals=["build platform"],
        primary_languages=["Python"],
        preferred_frameworks=["FastAPI"],
        working_domains=["Drones"],
        active_projects=["drone-platform"],
        recent_projects=[],
        generated_at=datetime.now(UTC),
        confidence=0.9,
        confidence_reason="test",
        profile_completeness=90,
    )


def _rich_project() -> ProjectContext:
    return ProjectContext(
        project_name="drone-platform",
        language="python",
        framework="fastapi",
        build_system="poetry",
        database=["postgres"],
        infrastructure=["docker"],
        ci_cd=["github-actions"],
        modules=["api"],
        generated_at=datetime.now(UTC),
    )


def _patch_planning(monkeypatch, tmp_path):
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    monkeypatch.setattr("smith.services.planner.UserContextService.load", lambda self: _rich_user())
    monkeypatch.setattr(
        "smith.services.planner.ProjectContextService.load",
        lambda self, path: _rich_project(),
    )
    monkeypatch.setattr(
        "smith.services.planner.WorkspaceIntelligenceService.load_workspace_context",
        lambda self: None,
    )
    monkeypatch.setattr("smith.services.planner.try_get_repository_status", lambda path: None)


def test_plan_answer_requires_session(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["plan", "answer", 'timeline="3 months"'])
    assert result.exit_code != 0


def test_plan_answer_updates_gaps(tmp_path, monkeypatch):
    _patch_planning(monkeypatch, tmp_path)
    monkeypatch.chdir(tmp_path)
    service = PlanningService(cwd=tmp_path)
    initial = service.create_plan("build drone platform")
    set_last_planning_result(initial)

    before = {g.dimension for g in service.build_context(initial.goal).gaps if g.dimension}
    result = runner.invoke(app, ["plan", "answer", 'timeline="3 months"'])
    assert result.exit_code == 0
    assert "Remaining Gaps" in result.output or "No remaining questions" in result.output

    after_ctx = service.build_context(initial.goal)
    after = {g.dimension for g in after_ctx.gaps if g.dimension}
    if PlanningDimension.TIMELINE in before:
        assert PlanningDimension.TIMELINE not in after


def test_plan_answer_cli_after_plan(tmp_path, monkeypatch):
    _patch_planning(monkeypatch, tmp_path)
    monkeypatch.chdir(tmp_path)
    plan_result = runner.invoke(app, ["plan", "build", "drone", "platform"])
    assert plan_result.exit_code == 0
    answer_result = runner.invoke(app, ["plan", "answer", 'timeline="Q3"'])
    assert answer_result.exit_code == 0


def test_rebuild_after_answer_reduces_questions(tmp_path, monkeypatch):
    _patch_planning(monkeypatch, tmp_path)
    service = PlanningService(cwd=tmp_path)
    result = service.create_plan("build drone platform")
    before_count = len(result.questions)
    service.record_decision(PlanningDimension.TIMELINE, "3 months")
    ctx = service.build_context(result.goal)
    from smith.services.clarification import generate_questions_from_gaps

    after_count = len(generate_questions_from_gaps(ctx.gaps))
    assert after_count <= before_count
