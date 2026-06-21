from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from smith.models.planning_context import PlanningReadiness
from smith.models.status import StatusRecommendation
from smith.services.status_dashboard import (
    StatusDashboardService,
    _dedupe_recommendations,
    format_cache_age,
    format_status_dashboard,
)
from tests.helpers.git_repo import init_git_repo
from tests.helpers.workspace_fixture import init_workspace


def test_format_cache_age_today():
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert format_cache_age(now) == "Today"


def test_format_cache_age_missing():
    assert format_cache_age(None) == "Missing"


def test_format_cache_age_hours():
    past = (datetime.now(UTC) - timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert format_cache_age(past) == "5 hours ago"


def test_format_cache_age_days():
    past = (datetime.now(UTC) - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert format_cache_age(past) == "3 days ago"


def test_dedupe_recommendations():
    recs = [
        StatusRecommendation(text="Run health", source="cache", command="smith health"),
        StatusRecommendation(text="run health", source="cache", command="smith health"),
        StatusRecommendation(
            text="Refresh context", source="cache", command="smith refresh-context ."
        ),
    ]
    result = _dedupe_recommendations(recs)
    assert len(result) == 2


def test_health_cache_round_trip(tmp_path):
    from smith.models.workstation_health import WorkstationHealthReport
    from smith.services.workstation_health import (
        load_workstation_health_cache,
        save_workstation_health_cache,
    )

    report = WorkstationHealthReport(
        score=85,
        score_breakdown={},
        issues=["Low disk space"],
        recommendations=[],
        correlations=[],
        findings=[],
        sections=[],
        scanned_paths=["~/Downloads"],
    )
    save_workstation_health_cache(tmp_path, report)
    loaded = load_workstation_health_cache(tmp_path)
    assert loaded is not None
    assert loaded.score == 85
    assert loaded.issues == ["Low disk space"]


def test_build_report_uses_load_not_build(tmp_path):
    workspace = init_workspace(tmp_path, project_count=1)
    project = workspace / "project-0"
    service = StatusDashboardService(project)

    with (
        patch(
            "smith.services.status_dashboard.ProjectContextService.load",
            return_value=None,
        ) as load_ctx,
        patch(
            "smith.services.status_dashboard.WorkspaceIntelligenceService.load_workspace_context",
            return_value=None,
        ) as load_ws,
        patch(
            "smith.services.status_dashboard.load_workstation_health_cache",
            return_value=None,
        ),
        patch(
            "smith.services.status_dashboard.PlanningService.assess_readiness",
            return_value=PlanningReadiness(
                known_count=0,
                gap_count=0,
                critical_gap_count=0,
                important_gap_count=0,
                assumption_count=0,
                constraint_count=0,
                context_quality=0.0,
                confidence=0.0,
                status="Insufficient Context",
            ),
        ),
    ):
        report = service.build_report()
        load_ctx.assert_called_once()
        load_ws.assert_called_once()

    assert report.project_context is None
    assert report.workspace_summary is None


def test_missing_cache_refresh_commands(tmp_path):
    workspace = init_workspace(tmp_path, project_count=1)
    report = StatusDashboardService(workspace).build_report()
    commands = {r.command for r in report.recommendations if r.command}
    assert "smith refresh-context ." in commands or any(
        "refresh-context" in r.text for r in report.recommendations
    )


def test_activity_score_not_in_format_output(tmp_path):
    workspace = init_workspace(tmp_path, project_count=1)
    from smith.services.workspace_intelligence import WorkspaceIntelligenceService

    service = WorkspaceIntelligenceService(workspace)
    summary = service.build_workspace_summary()
    service.save_workspace_context(summary)
    report = StatusDashboardService(workspace).build_report()
    text = format_status_dashboard(report)
    content_lines = [ln for ln in text.splitlines() if "activity_score" not in ln.lower()]
    assert len(content_lines) == len(text.splitlines())


def test_git_commit_suggestion_when_changes(tmp_path):
    repo = init_git_repo(tmp_path)
    (repo / "new_feature.py").write_text("x = 1\n")
    report = StatusDashboardService(repo).build_report()
    assert report.git_health is not None
    assert report.commit_suggestion is not None
