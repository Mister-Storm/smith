from datetime import UTC, datetime, timedelta

import pytest

from smith.core.exceptions import WorkspaceNoProjectsError
from smith.models.workspace import WORKSPACE_SCHEMA_VERSION, ProjectStatus
from smith.services.gitignore import ensure_smith_gitignore_entry
from smith.services.workspace_intelligence import (
    WorkspaceIntelligenceService,
    compute_activity_score,
    format_last_activity,
)
from smith.tools.fs_utils import should_skip_workspace_dir
from tests.helpers.git_repo import init_git_repo
from tests.helpers.workspace_fixture import create_python_project, init_workspace


def test_should_skip_workspace_dir():
    assert should_skip_workspace_dir("node_modules")
    assert should_skip_workspace_dir(".smith")
    assert not should_skip_workspace_dir("src")


def test_discover_projects(tmp_path):
    workspace = init_workspace(tmp_path, project_count=2)
    service = WorkspaceIntelligenceService(workspace, max_depth=3)
    projects = service.discover_projects()
    assert len(projects) == 2


def test_discover_respects_depth(tmp_path):
    workspace = tmp_path / "root"
    workspace.mkdir()
    deep = workspace / "a" / "b" / "c" / "deep-project"
    deep.mkdir(parents=True)
    (deep / "pyproject.toml").write_text("[project]\nname='deep'\n")

    create_python_project(workspace, "shallow", with_git=False)

    service = WorkspaceIntelligenceService(workspace, max_depth=2)
    projects = service.discover_projects()
    names = {p.name for p in projects}
    assert "shallow" in names
    assert "deep-project" not in names


def test_no_projects_raises(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    service = WorkspaceIntelligenceService(empty)
    with pytest.raises(WorkspaceNoProjectsError, match="No projects were detected"):
        service.build_workspace_summary()


def test_single_project_warning(tmp_path):
    workspace = tmp_path / "solo"
    workspace.mkdir()
    create_python_project(workspace, "only")
    summary = WorkspaceIntelligenceService(workspace).build_workspace_summary()
    assert summary.project_count == 1
    assert any("single project" in w.lower() for w in summary.warnings)


def test_activity_score_ranking():
    high = compute_activity_score(modified_files=5, staged_files=2, last_commit_date=None)
    low = compute_activity_score(modified_files=0, staged_files=0, last_commit_date=None)
    assert high > low


def test_format_last_activity_today():
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert format_last_activity(now) == "Today"


def test_format_last_activity_unknown():
    assert format_last_activity(None) == "Unknown"


def test_format_last_activity_days_ago():
    past = (datetime.now(UTC) - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert format_last_activity(past) == "3 days ago"


def test_summary_sorts_by_activity_score(tmp_path):
    workspace = init_workspace(tmp_path, project_count=2)
    active = workspace / "project-0"
    (active / "changes.py").write_text("x = 1\n")
    summary = WorkspaceIntelligenceService(workspace).build_workspace_summary()
    assert summary.projects[0].activity_score >= summary.projects[-1].activity_score


def test_activity_score_not_in_format_output(tmp_path):
    workspace = init_workspace(tmp_path, project_count=1)
    summary = WorkspaceIntelligenceService(workspace).build_workspace_summary()
    from smith.services.workspace_intelligence import format_workspace_summary

    text = format_workspace_summary(summary)
    content_lines = [ln for ln in text.splitlines() if not ln.strip().startswith("Root:")]
    assert not any("activity_score" in ln for ln in content_lines)


def test_workspace_health_counts(tmp_path):
    workspace = init_workspace(tmp_path, project_count=2)
    health = WorkspaceIntelligenceService(workspace).build_workspace_health()
    assert health.total_projects == 2
    assert health.projects_without_readme == 0


def test_schema_version_on_save_and_load(tmp_path):
    workspace = init_workspace(tmp_path, project_count=2)
    service = WorkspaceIntelligenceService(workspace)
    summary = service.build_workspace_summary()
    service.save_workspace_context(summary)
    loaded = service.load_workspace_context()
    assert loaded is not None
    assert loaded.schema_version == WORKSPACE_SCHEMA_VERSION


def test_schema_version_defaults_when_missing():
    from smith.models.workspace import WorkspaceSummary

    data = {
        "root": "/tmp",
        "project_count": 0,
        "languages": {},
        "frameworks": {},
        "active_projects": [],
        "stale_projects": [],
        "generated_at": "2026-01-01T00:00:00Z",
        "projects": [],
    }
    summary = WorkspaceSummary.from_dict(data)
    assert summary.schema_version == WORKSPACE_SCHEMA_VERSION


def test_max_projects_limit(tmp_path, monkeypatch):
    workspace = tmp_path / "many"
    workspace.mkdir()
    monkeypatch.setattr(
        "smith.services.workspace_intelligence.MAX_PROJECTS",
        2,
    )
    for i in range(3):
        create_python_project(workspace, f"p{i}", with_git=False)
    summary = WorkspaceIntelligenceService(workspace).build_workspace_summary()
    assert summary.project_count == 2
    assert any("stopped after" in w for w in summary.warnings)


def test_gitignore_appends_smith_entry(tmp_path):
    repo = init_git_repo(tmp_path)
    (repo / ".gitignore").write_text("*.pyc\n")
    ensure_smith_gitignore_entry(repo)
    content = (repo / ".gitignore").read_text()
    assert ".smith/*" in content
    assert "!.smith/.gitkeep" in content


def test_gitignore_no_duplicate(tmp_path):
    repo = init_git_repo(tmp_path)
    (repo / ".gitignore").write_text(".smith/*\n!.smith/.gitkeep\n")
    ensure_smith_gitignore_entry(repo)
    assert (repo / ".gitignore").read_text().count(".smith/*") == 1


def test_gitignore_no_create_when_missing(tmp_path):
    repo = init_git_repo(tmp_path)
    ensure_smith_gitignore_entry(repo)
    assert not (repo / ".gitignore").exists()


def test_project_status_active_with_changes(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    project = create_python_project(workspace, "active-proj")
    (project / "new.py").write_text("x=1\n")
    summary = WorkspaceIntelligenceService(workspace).build_workspace_summary()
    assert summary.projects[0].status == ProjectStatus.ACTIVE
    assert summary.projects[0].last_activity in ("Today", "Unknown", "Yesterday")
