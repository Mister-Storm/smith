from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from smith.models.planning_context import (
    ContextGap,
    GapSeverity,
    PlanningDimension,
)
from smith.models.project_context import ProjectContext
from smith.models.user_context import UserContext
from smith.models.workspace import WorkspaceSummary
from smith.services.planner import (
    MAX_ASSUMPTIONS,
    PlanningService,
    can_generate_plan,
)
from tests.conftest import FakeLLMProvider


def _rich_user() -> UserContext:
    return UserContext(
        interests=["drones"],
        goals=["build platform"],
        primary_languages=["Python", "Kotlin"],
        preferred_frameworks=["FastAPI", "Spring Boot"],
        working_domains=["Drones"],
        active_projects=["drone-platform", "smith"],
        recent_projects=["legacy-app"],
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
        modules=["api", "services"],
        generated_at=datetime.now(UTC),
    )


def _workspace() -> WorkspaceSummary:
    return WorkspaceSummary(
        root="/tmp",
        project_count=1,
        active_projects=["drone-platform"],
        stale_projects=[],
        projects=[],
        languages={"Python": 1},
        frameworks={"FastAPI": 1},
        generated_at=datetime.now(UTC).isoformat(),
    )


@pytest.fixture
def planning_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace


def test_can_generate_plan_requires_thresholds():
    ok, _ = can_generate_plan(0.7, known_count=5, critical_gap_count=0, important_gap_count=1, assumption_count=1)
    assert ok
    allowed, reason = can_generate_plan(
        0.7, known_count=5, critical_gap_count=1, important_gap_count=0, assumption_count=1
    )
    assert not allowed
    assert "critical" in reason.lower()
    allowed, reason = can_generate_plan(
        0.7, known_count=5, critical_gap_count=0, important_gap_count=1, assumption_count=MAX_ASSUMPTIONS + 1
    )
    assert not allowed
    assert "assumption" in reason.lower()


def test_assumption_budget_blocks_planning(planning_env, monkeypatch):
    user = _rich_user()
    project = _rich_project()

    monkeypatch.setattr(
        "smith.services.planner.UserContextService.load",
        lambda self: user,
    )
    monkeypatch.setattr(
        "smith.services.planner.ProjectContextService.load",
        lambda self, path: project,
    )
    monkeypatch.setattr(
        "smith.services.planner.WorkspaceIntelligenceService.load_workspace_context",
        lambda self: _workspace(),
    )
    monkeypatch.setattr("smith.services.planner.try_get_repository_status", lambda path: None)

    service = PlanningService(cwd=planning_env)
    ctx = service.build_context("build drone platform")
    ctx.assumptions = ["Assuming A", "Assuming B", "Assuming C", "Assuming D"]
    mode, _, _ = service.evaluate_readiness(ctx)
    assert mode == "clarification_required"


def test_critical_gaps_block_planning(planning_env, monkeypatch):
    user = _rich_user()
    project = _rich_project()
    monkeypatch.setattr("smith.services.planner.UserContextService.load", lambda self: user)
    monkeypatch.setattr(
        "smith.services.planner.ProjectContextService.load", lambda self, path: project
    )
    monkeypatch.setattr(
        "smith.services.planner.WorkspaceIntelligenceService.load_workspace_context",
        lambda self: _workspace(),
    )
    monkeypatch.setattr("smith.services.planner.try_get_repository_status", lambda path: None)

    service = PlanningService(cwd=planning_env)
    ctx = service.build_context("build drone platform")
    ctx.gaps.append(
        ContextGap(
            name="Timeline",
            dimension=PlanningDimension.TIMELINE,
            reason="missing",
            severity=GapSeverity.CRITICAL,
            source="Gap Analysis",
        )
    )
    mode, _, _ = service.evaluate_readiness(ctx)
    assert mode == "clarification_required"


def test_llm_not_called_when_blocked(planning_env, monkeypatch):
    user = _rich_user()
    monkeypatch.setattr("smith.services.planner.UserContextService.load", lambda self: user)
    monkeypatch.setattr(
        "smith.services.planner.ProjectContextService.load", lambda self, path: None
    )
    monkeypatch.setattr(
        "smith.services.planner.WorkspaceIntelligenceService.load_workspace_context",
        lambda self: _workspace(),
    )
    monkeypatch.setattr("smith.services.planner.try_get_repository_status", lambda path: None)

    llm = FakeLLMProvider(response="# Plan\n1. step")
    service = PlanningService(cwd=planning_env, provider=llm)
    result = service.create_plan("build something")
    assert result.plan is None
    assert len(llm.calls) == 0


def test_llm_plan_only_when_ready(planning_env, monkeypatch):
    user = _rich_user()
    project = _rich_project()
    monkeypatch.setattr("smith.services.planner.UserContextService.load", lambda self: user)
    monkeypatch.setattr(
        "smith.services.planner.ProjectContextService.load", lambda self, path: project
    )
    monkeypatch.setattr(
        "smith.services.planner.WorkspaceIntelligenceService.load_workspace_context",
        lambda self: _workspace(),
    )
    monkeypatch.setattr("smith.services.planner.try_get_repository_status", lambda path: None)

    llm = FakeLLMProvider(response="# Goal\n# Plan\n1. Step one")
    service = PlanningService(cwd=planning_env, provider=llm)

    with patch.object(service, "evaluate_readiness", return_value=("ready_to_plan", 0.9, [])):
        with patch.object(service, "generate_plan", return_value="# Plan\n1. Step one") as gen:
            result = service.create_plan("build api backend", force_plan=True)
    assert result.planning_mode == "ready_to_plan"
    assert result.plan is not None
    gen.assert_called_once()
