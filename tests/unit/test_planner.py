from datetime import UTC, datetime

from smith.models.project_context import ProjectContext
from smith.models.user_context import UserContext
from smith.services.planner import PlanningService


def _user() -> UserContext:
    return UserContext(
        interests=["ai"],
        goals=["build assistant"],
        primary_languages=["Python"],
        preferred_frameworks=["FastAPI"],
        working_domains=["AI Assistants"],
        active_projects=["smith"],
        recent_projects=[],
        generated_at=datetime.now(UTC),
        confidence=0.7,
        confidence_reason="",
        profile_completeness=70,
    )


def _project() -> ProjectContext:
    return ProjectContext(
        project_name="smith",
        language="python",
        framework="fastapi",
        build_system="poetry",
        database=[],
        infrastructure=["docker"],
        ci_cd=["github-actions"],
        modules=[],
        generated_at=datetime.now(UTC),
    )


def test_build_context_assembles_knowns_and_gaps(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    monkeypatch.setattr("smith.services.planner.UserContextService.load", lambda self: _user())
    monkeypatch.setattr(
        "smith.services.planner.ProjectContextService.load",
        lambda self, path: _project(),
    )
    monkeypatch.setattr(
        "smith.services.planner.WorkspaceIntelligenceService.load_workspace_context",
        lambda self: None,
    )
    monkeypatch.setattr("smith.services.planner.try_get_repository_status", lambda path: None)

    service = PlanningService(cwd=tmp_path)
    ctx = service.build_context("build local ai assistant")
    assert ctx.knowns
    assert any("Docker" in known.text for known in ctx.knowns)
    assert ctx.gaps
    assert not hasattr(ctx, "goal_domain")


def test_assess_readiness_no_ai(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    monkeypatch.setattr("smith.services.planner.UserContextService.load", lambda self: _user())
    monkeypatch.setattr(
        "smith.services.planner.ProjectContextService.load", lambda self, path: _project()
    )
    monkeypatch.setattr(
        "smith.services.planner.WorkspaceIntelligenceService.load_workspace_context",
        lambda self: None,
    )
    monkeypatch.setattr("smith.services.planner.try_get_repository_status", lambda path: None)

    service = PlanningService(cwd=tmp_path)
    readiness = service.assess_readiness(None)
    assert readiness.known_count >= 1
    assert readiness.gap_count >= 0
    assert readiness.status
