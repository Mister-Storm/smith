"""Unified status dashboard aggregation for smith status."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from smith.core.config import Config, describe_provider_selection, get_active_model, get_smith_home
from smith.core.exceptions import GitNotRepositoryError
from smith.models.git_intelligence import DevelopmentAssessment
from smith.models.status import (
    CacheFreshness,
    EnvironmentInfo,
    StatusRecommendation,
    StatusReport,
)
from smith.services.doctor import CheckStatus, run_doctor
from smith.services.git_intelligence import GitIntelligenceService, try_get_repository_status
from smith.services.project_context import (
    ProjectContextService,
    display_build,
    display_framework,
    display_language,
)
from smith.services.workspace_intelligence import WorkspaceIntelligenceService
from smith.services.workstation_health import load_workstation_health_cache

logger = logging.getLogger(__name__)

STALE_CACHE_DAYS = 7

PROJECT_REFRESH = "smith refresh-context ."
WORKSPACE_REFRESH = "smith workspace ."
HEALTH_REFRESH = "smith health"


def _display_path(path: Path) -> str:
    home = Path.home()
    try:
        return f"~/{path.relative_to(home)}"
    except ValueError:
        return str(path)


def _parse_timestamp(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def format_cache_age(value: str | datetime | None) -> str:
    dt = _parse_timestamp(value)
    if dt is None:
        return "Missing"

    now = datetime.now(UTC)
    delta = now - dt
    if delta.total_seconds() < 0:
        return "Today"
    if delta.days == 0:
        hours = int(delta.total_seconds() // 3600)
        if hours == 0:
            return "Today"
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    if delta.days == 1:
        return "Yesterday"
    if delta.days < 7:
        return f"{delta.days} days ago"
    weeks = delta.days // 7
    if weeks < 5:
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    months = delta.days // 30
    if months < 12:
        return f"{months} month{'s' if months != 1 else ''} ago"
    years = delta.days // 365
    return f"{years} year{'s' if years != 1 else ''} ago"


def _is_stale(value: str | datetime | None) -> bool:
    dt = _parse_timestamp(value)
    if dt is None:
        return True
    return datetime.now(UTC) - dt > timedelta(days=STALE_CACHE_DAYS)


def _dedupe_recommendations(recs: list[StatusRecommendation]) -> list[StatusRecommendation]:
    seen: set[str] = set()
    result: list[StatusRecommendation] = []
    for rec in recs:
        key = rec.text.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(rec)
    return result


class StatusDashboardService:
    """Cache-first workstation overview for smith status."""

    def __init__(self, cwd: Path | None = None) -> None:
        self._cwd = (cwd or Path.cwd()).expanduser().resolve()

    def build_report(self) -> StatusReport:
        config = Config.load()
        provider_label, _ = describe_provider_selection(config)
        model = get_active_model(config)
        memory_db = _display_path(config.db_path)
        config_path = _display_path(get_smith_home() / "config.toml")

        environment = EnvironmentInfo(
            provider=provider_label,
            model=model,
            memory_db=memory_db,
            config_path=config_path,
        )

        doctor = run_doctor(config=config)
        project_context = ProjectContextService().load(self._cwd)
        workspace_summary = WorkspaceIntelligenceService(self._cwd).load_workspace_context()
        workstation_health = load_workstation_health_cache(self._cwd)

        git_health = None
        commit_suggestion = None
        repo_status = try_get_repository_status(self._cwd)
        if repo_status is not None:
            try:
                git = GitIntelligenceService(cwd=self._cwd)
                git_health = git.get_git_health()
                suggestions = git.suggest_commit_messages()
                if suggestions:
                    commit_suggestion = suggestions[0].message
            except GitNotRepositoryError:
                pass

        cache_freshness = self._build_cache_freshness(
            project_context, workspace_summary, workstation_health
        )
        recommendations = self._build_recommendations(
            doctor=doctor,
            project_context=project_context,
            workspace_summary=workspace_summary,
            workstation_health=workstation_health,
            cache_freshness=cache_freshness,
            repo_status=repo_status,
            commit_suggestion=commit_suggestion,
        )
        warnings: list[str] = []
        if workspace_summary and workspace_summary.warnings:
            warnings.extend(workspace_summary.warnings)

        return StatusReport(
            cwd=str(self._cwd),
            environment=environment,
            cache_freshness=cache_freshness,
            doctor_sections=doctor.sections,
            workstation_health=workstation_health,
            project_context=project_context,
            workspace_summary=workspace_summary,
            git_health=git_health,
            commit_suggestion=commit_suggestion,
            recommendations=recommendations,
            warnings=warnings,
        )

    def _build_cache_freshness(
        self,
        project_context,
        workspace_summary,
        workstation_health,
    ) -> list[CacheFreshness]:
        project_at = project_context.generated_at.isoformat() if project_context else None
        workspace_at = workspace_summary.generated_at if workspace_summary else None
        health_at = workstation_health.generated_at if workstation_health else None

        return [
            CacheFreshness(
                label="Project Context",
                status=format_cache_age(project_at),
                generated_at=project_at,
                refresh_command=PROJECT_REFRESH,
            ),
            CacheFreshness(
                label="Workspace Context",
                status=format_cache_age(workspace_at),
                generated_at=workspace_at,
                refresh_command=WORKSPACE_REFRESH,
            ),
            CacheFreshness(
                label="Workstation Health",
                status=format_cache_age(health_at),
                generated_at=health_at,
                refresh_command=HEALTH_REFRESH,
            ),
        ]

    def _build_recommendations(
        self,
        *,
        doctor,
        project_context,
        workspace_summary,
        workstation_health,
        cache_freshness,
        repo_status,
        commit_suggestion,
    ) -> list[StatusRecommendation]:
        recs: list[StatusRecommendation] = []

        if workstation_health:
            for item in workstation_health.recommendations:
                text = item.title
                recs.append(
                    StatusRecommendation(text=text, source="health", command=item.suggested_command)
                )

        if workspace_summary:
            for warning in workspace_summary.warnings:
                recs.append(StatusRecommendation(text=warning, source="workspace", command=None))

        for title, check in doctor.sections:
            if check.status in (CheckStatus.WARN, CheckStatus.CRITICAL):
                for line in check.lines:
                    if line and not line.startswith("  "):
                        recs.append(
                            StatusRecommendation(
                                text=f"{title}: {line}",
                                source="doctor",
                                command="smith doctor",
                            )
                        )

        for freshness in cache_freshness:
            if freshness.status == "Missing" or _is_stale(freshness.generated_at):
                label = freshness.label
                if freshness.status == "Missing":
                    text = f"{label} is not cached — run `{freshness.refresh_command}`"
                else:
                    text = (
                        f"{label} is stale ({freshness.status}) — run `{freshness.refresh_command}`"
                    )
                recs.append(
                    StatusRecommendation(
                        text=text,
                        source="cache",
                        command=freshness.refresh_command,
                    )
                )

        if repo_status and repo_status.assessment in (
            DevelopmentAssessment.WORK_IN_PROGRESS,
            DevelopmentAssessment.READY_FOR_COMMIT,
        ):
            if commit_suggestion:
                recs.append(
                    StatusRecommendation(
                        text=f"Suggested commit: {commit_suggestion}",
                        source="git",
                        command="smith git commit-message",
                    )
                )

        return _dedupe_recommendations(recs)


def format_status_dashboard(report: StatusReport) -> str:
    lines = [
        "Smith Status",
        "",
        "Environment",
        f"  Provider: {report.environment.provider}",
        f"  Model: {report.environment.model}",
        f"  Memory DB: {report.environment.memory_db}",
        f"  Config: {report.environment.config_path}",
        "",
        "Cache Freshness",
    ]
    for item in report.cache_freshness:
        lines.append(f"  {item.label}: {item.status}")

    lines.extend(["", "Workstation Health"])
    if report.workstation_health:
        wh = report.workstation_health
        lines.append(f"  Score: {wh.score}/100")
        for issue in wh.issues[:3]:
            lines.append(f"  - {issue}")
    else:
        lines.append("  Not cached — run `smith health`")

    lines.extend(["", "Workspace Summary"])
    if report.workspace_summary:
        ws = report.workspace_summary
        lines.append(f"  Projects: {ws.project_count}")
        if ws.active_projects:
            lines.append(f"  Active: {', '.join(ws.active_projects[:5])}")
        for project in ws.projects[:5]:
            lines.append(f"  • {project.name} ({project.last_activity})")
    else:
        lines.append("  Not cached — run `smith workspace .`")

    lines.extend(["", "Current Project"])
    if report.project_context:
        ctx = report.project_context
        lines.append(f"  Name: {ctx.project_name}")
        lines.append(f"  Language: {display_language(ctx.language)}")
        lines.append(f"  Framework: {display_framework(ctx.framework)}")
        lines.append(f"  Build: {display_build(ctx.build_system)}")
        db = ", ".join(ctx.database) if ctx.database else "—"
        lines.append(f"  Database: {db}")
        lines.append(f"  Generated: {format_cache_age(ctx.generated_at)}")
    else:
        lines.append("  Not cached — run `smith refresh-context .`")

    lines.extend(["", "Git Status"])
    if report.git_health:
        gh = report.git_health
        lines.append(f"  Branch: {gh.branch}")
        lines.append(f"  Modified: {gh.modified}")
        lines.append(f"  Untracked: {gh.untracked}")
        if report.commit_suggestion:
            lines.append(f"  Suggested: {report.commit_suggestion}")
    else:
        lines.append("  Not a git repository")

    if report.recommendations:
        lines.extend(["", "Recommendations"])
        for rec in report.recommendations:
            cmd = f" → {rec.command}" if rec.command else ""
            lines.append(f"  - {rec.text}{cmd}")

    return "\n".join(lines)


def render_status_dashboard(report: StatusReport, console) -> None:
    from rich.markup import escape
    from rich.panel import Panel
    from rich.table import Table

    console.print("[bold]Smith Status[/bold]\n")

    env_table = Table(title="Environment", show_header=True, header_style="bold")
    env_table.add_column("Field")
    env_table.add_column("Value")
    env_table.add_row("Provider", report.environment.provider)
    env_table.add_row("Model", report.environment.model)
    env_table.add_row("Memory DB", report.environment.memory_db)
    env_table.add_row("Config", report.environment.config_path)
    console.print(env_table)
    console.print()

    cache_table = Table(title="Cache Freshness", show_header=True, header_style="bold")
    cache_table.add_column("Artifact")
    cache_table.add_column("Age")
    for item in report.cache_freshness:
        cache_table.add_row(item.label, item.status)
    console.print(cache_table)
    console.print()

    if report.workstation_health:
        wh = report.workstation_health
        wh_lines = [f"Score: {wh.score}/100"]
        for issue in wh.issues[:5]:
            wh_lines.append(f"• {issue}")
        console.print(
            Panel(
                "\n".join(escape(ln) for ln in wh_lines),
                title="Workstation Health",
                border_style="cyan",
                expand=False,
            )
        )
    else:
        console.print(
            Panel(
                "Not cached — run [bold]smith health[/bold]",
                title="Workstation Health",
                border_style="yellow",
                expand=False,
            )
        )
    console.print()

    if report.workspace_summary:
        ws = report.workspace_summary
        ws_lines = [f"Projects discovered: {ws.project_count}"]
        if ws.active_projects:
            ws_lines.append(f"Active: {', '.join(ws.active_projects[:5])}")
        ws_lines.append("")
        ws_lines.append("Most active:")
        for project in ws.projects[:5]:
            ws_lines.append(f"• {project.name} ({project.last_activity})")
        console.print(
            Panel(
                "\n".join(escape(ln) for ln in ws_lines),
                title="Workspace Summary",
                border_style="cyan",
                expand=False,
            )
        )
    else:
        console.print(
            Panel(
                "Not cached — run [bold]smith workspace .[/bold]",
                title="Workspace Summary",
                border_style="yellow",
                expand=False,
            )
        )
    console.print()

    if report.project_context:
        ctx = report.project_context
        db = ", ".join(ctx.database) if ctx.database else "—"
        proj_table = Table(title="Current Project", show_header=True, header_style="bold")
        proj_table.add_column("Field")
        proj_table.add_column("Value")
        proj_table.add_row("Name", ctx.project_name)
        proj_table.add_row("Language", display_language(ctx.language))
        proj_table.add_row("Framework", display_framework(ctx.framework))
        proj_table.add_row("Build System", display_build(ctx.build_system))
        proj_table.add_row("Database", db)
        proj_table.add_row("Generated", format_cache_age(ctx.generated_at))
        console.print(proj_table)
    else:
        console.print(
            Panel(
                "Not cached — run [bold]smith refresh-context .[/bold]",
                title="Current Project",
                border_style="yellow",
                expand=False,
            )
        )
    console.print()

    if report.git_health:
        gh = report.git_health
        git_table = Table(title="Git Status", show_header=True, header_style="bold")
        git_table.add_column("Field")
        git_table.add_column("Value")
        git_table.add_row("Branch", gh.branch)
        git_table.add_row("Modified", str(gh.modified))
        git_table.add_row("Untracked", str(gh.untracked))
        if report.commit_suggestion:
            git_table.add_row("Suggested Commit", report.commit_suggestion)
        console.print(git_table)
    else:
        console.print(
            Panel(
                "Not a git repository",
                title="Git Status",
                border_style="dim",
                expand=False,
            )
        )
    console.print()

    if report.warnings:
        console.print(
            Panel(
                "\n".join(escape(w) for w in report.warnings),
                title="Warnings",
                border_style="yellow",
                expand=False,
            )
        )
        console.print()

    if report.recommendations:
        rec_table = Table(title="Recommendations", show_header=True, header_style="bold")
        rec_table.add_column("Recommendation")
        rec_table.add_column("Action")
        for rec in report.recommendations:
            rec_table.add_row(rec.text, rec.command or "—")
        console.print(rec_table)
