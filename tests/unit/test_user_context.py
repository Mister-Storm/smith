from datetime import UTC, datetime, timedelta

from smith.models.project_context import ProjectContext
from smith.models.user_context import UserContext
from smith.services.context_inference import (
    apply_inference,
    build_compact_summary,
    infer_project_context,
    parse_inference_response,
    should_infer,
)
from smith.services.domain_mapping import top_domains
from smith.services.user_context import (
    UserContextService,
    compute_profile_completeness,
)
from tests.helpers.workspace_fixture import init_workspace


def _ctx(**kwargs) -> ProjectContext:
    defaults = dict(
        project_name="test",
        language="python",
        framework="fastapi",
        build_system="poetry",
        database=["sqlite"],
        infrastructure=[],
        ci_cd=[],
        modules=[],
        generated_at=datetime.now(UTC),
    )
    defaults.update(kwargs)
    return ProjectContext(**defaults)


def test_top_domains_from_project_names():
    domains = top_domains(["smith", "drone-platform", "smith-ai"])
    assert "AI Assistants" in domains or "Drones" in domains


def test_compute_profile_completeness():
    ctx = UserContext(
        interests=["drones"],
        goals=[],
        primary_languages=["Python"],
        preferred_frameworks=["FastAPI"],
        working_domains=["AI Assistants"],
        active_projects=["smith"],
        recent_projects=["smith"],
        generated_at=datetime.now(UTC),
        confidence=0.8,
        confidence_reason="test",
        profile_completeness=0,
    )
    result = compute_profile_completeness(ctx)
    assert result.score < 100
    assert "goals" in result.missing


def test_freshness_helpers():
    ctx = UserContext(
        interests=[],
        goals=[],
        primary_languages=[],
        preferred_frameworks=[],
        working_domains=[],
        active_projects=[],
        recent_projects=[],
        generated_at=datetime.now(UTC) - timedelta(days=20),
        confidence=0.5,
        confidence_reason="",
        profile_completeness=0,
    )
    assert ctx.age_days() == 20
    assert ctx.freshness_status() == "Needs Refresh"
    assert not ctx.is_stale()

    stale = UserContext(
        interests=[],
        goals=[],
        primary_languages=[],
        preferred_frameworks=[],
        working_domains=[],
        active_projects=[],
        recent_projects=[],
        generated_at=datetime.now(UTC) - timedelta(days=45),
        confidence=0.5,
        confidence_reason="",
        profile_completeness=0,
    )
    assert stale.is_stale()


def test_user_overrides_preserved_on_refresh(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    workspace = init_workspace(tmp_path, project_count=1)
    service = UserContextService(workspace)
    service.set_interest("drones")
    service.set_goal("build-smith")
    service.refresh()
    profile = service.load()
    assert "drones" in profile.interests
    assert "build-smith" in profile.goals


def test_should_infer_when_gaps_and_low_confidence():
    ctx = _ctx(framework=None, build_system=None, database=[])
    assert should_infer(ctx, workspace_confidence=0.2) is True
    assert should_infer(ctx, workspace_confidence=0.9) is False


def test_should_not_infer_when_deterministic_present():
    ctx = _ctx()
    assert should_infer(ctx, workspace_confidence=0.2) is False


def test_apply_inference_does_not_overwrite():
    ctx = _ctx(framework="fastapi")
    from smith.services.context_inference import InferenceResult

    inference = InferenceResult(framework="django", build_system="poetry", database=["postgres"])
    merged = apply_inference(ctx, inference)
    assert merged.framework == "fastapi"
    assert merged.build_system == "poetry"
    assert merged.database == ["sqlite"]


def test_parse_inference_response():
    raw = '{"framework": "FastAPI", "database": ["sqlite"], "build_system": "poetry", "reason": "deps"}'
    result = parse_inference_response(raw)
    assert result is not None
    assert result.framework == "FastAPI"


def test_build_compact_summary(tmp_path):
    project = tmp_path / "drone-platform"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname='drone'\n")
    (project / "README.md").write_text("# Drone Platform\n")
    summary = build_compact_summary(project)
    assert "drone-platform" in summary
    assert "pyproject.toml" in summary


def test_infer_skipped_with_deterministic_framework(tmp_path):
    ctx = _ctx(framework="fastapi")
    result = infer_project_context(tmp_path, ctx, workspace_confidence=0.1)
    assert result is None


def test_explain_includes_provenance(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    workspace = init_workspace(tmp_path, project_count=1)
    from smith.services.project_context import ProjectContextService
    from smith.services.workspace_intelligence import WorkspaceIntelligenceService

    ws = WorkspaceIntelligenceService(workspace)
    summary = ws.build_workspace_summary()
    ws.save_workspace_context(summary)
    for p in ws.discover_projects():
        pcs = ProjectContextService()
        ctx, _ = pcs.build(p)
        pcs.save(p, ctx)

    service = UserContextService(workspace)
    service.refresh()
    explanation = service.explain()
    assert explanation.fields
