"""Workspace intelligence aggregation. Used by future status dashboard aggregation."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from smith.core.exceptions import WorkspaceNoProjectsError
from smith.models.workspace import (
    WORKSPACE_SCHEMA_VERSION,
    ProjectStatus,
    WorkspaceHealth,
    WorkspaceProject,
    WorkspaceSummary,
)
from smith.services.git_intelligence import try_get_last_commit_date, try_get_repository_status
from smith.services.gitignore import ensure_smith_gitignore_entry
from smith.services.project_context import (
    ProjectContextService,
    display_build,
    display_framework,
    display_language,
)
from smith.tools.fs_utils import WORKSPACE_SKIP_DIR_NAMES

logger = logging.getLogger(__name__)

# Aggregated by StatusDashboardService (smith status).

MAX_PROJECTS = 100

PROJECT_FILE_MARKERS = (
    "pyproject.toml",
    "build.gradle",
    "build.gradle.kts",
    "pom.xml",
    "package.json",
    "Cargo.toml",
    "go.mod",
)

SINGLE_PROJECT_WARNING = (
    "This directory appears to be a single project rather than a workspace. "
    "Consider running: smith context"
)

SCAN_LIMIT_WARNING = (
    "Workspace scan stopped after {limit} detected projects. Results may be incomplete."
)

README_NAMES = ("README.md", "README.rst", "Readme.md")

CONTEXT_DIR = ".smith"
WORKSPACE_CONTEXT_FILE = "workspace_context.json"


class WorkspaceIntelligenceService:
    """Used by future status dashboard aggregation."""

    def __init__(self, root: Path, *, max_depth: int = 3) -> None:
        self._root = root.expanduser().resolve()
        self._max_depth = max_depth
        self._context_service = ProjectContextService()
        self._scan_limit_hit = False

    @staticmethod
    def workspace_context_path(root: Path) -> Path:
        return root.expanduser().resolve() / CONTEXT_DIR / WORKSPACE_CONTEXT_FILE

    def discover_projects(self) -> list[Path]:
        projects: list[Path] = []
        self._scan_limit_hit = False

        def walk(directory: Path, depth: int) -> None:
            if self._scan_limit_hit or depth > self._max_depth:
                return
            if _is_project_directory(directory):
                projects.append(directory)
                if len(projects) >= MAX_PROJECTS:
                    self._scan_limit_hit = True
                return
            try:
                children = sorted(directory.iterdir(), key=lambda p: p.name)
            except OSError:
                return
            for child in children:
                if not child.is_dir():
                    continue
                if child.name in WORKSPACE_SKIP_DIR_NAMES:
                    continue
                if child.name.startswith(".") and child.name != ".":
                    continue
                walk(child, depth + 1)

        if _is_project_directory(self._root):
            projects.append(self._root)
        else:
            walk(self._root, 0)

        if len(projects) > MAX_PROJECTS:
            projects = projects[:MAX_PROJECTS]
            self._scan_limit_hit = True

        return projects

    def build_workspace_summary(self) -> WorkspaceSummary:
        project_paths = self.discover_projects()
        if not project_paths:
            raise WorkspaceNoProjectsError("No projects were detected in this workspace.")

        warnings: list[str] = []
        if self._scan_limit_hit:
            warnings.append(SCAN_LIMIT_WARNING.format(limit=MAX_PROJECTS))
        if len(project_paths) == 1:
            warnings.append(SINGLE_PROJECT_WARNING)

        projects: list[WorkspaceProject] = []
        languages: dict[str, int] = {}
        frameworks: dict[str, int] = {}
        active_projects: list[str] = []
        stale_projects: list[str] = []

        for project_path in project_paths:
            wp = self._build_workspace_project(project_path)
            projects.append(wp)
            if wp.language and wp.language != "—":
                languages[wp.language] = languages.get(wp.language, 0) + 1
            if wp.framework and wp.framework != "—":
                frameworks[wp.framework] = frameworks.get(wp.framework, 0) + 1
            if wp.status == ProjectStatus.ACTIVE:
                active_projects.append(wp.name)
            if _is_stale_project(project_path, wp.last_commit_date):
                stale_projects.append(wp.name)

        projects.sort(key=lambda p: p.activity_score, reverse=True)

        return WorkspaceSummary(
            schema_version=WORKSPACE_SCHEMA_VERSION,
            root=str(self._root),
            project_count=len(projects),
            languages=languages,
            frameworks=frameworks,
            active_projects=active_projects,
            stale_projects=stale_projects,
            generated_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            projects=projects,
            warnings=warnings,
        )

    def build_workspace_health(self) -> WorkspaceHealth:
        project_paths = self.discover_projects()
        if not project_paths:
            raise WorkspaceNoProjectsError("No projects were detected in this workspace.")

        without_readme = 0
        without_ci = 0
        without_tests = 0
        stale = 0
        healthy = 0

        for project_path in project_paths:
            has_readme = _has_readme(project_path)
            has_ci = _has_ci(project_path)
            has_tests = _has_tests(project_path)
            last_commit = try_get_last_commit_date(project_path)
            is_stale = _is_stale_project(project_path, last_commit)

            if not has_readme:
                without_readme += 1
            if not has_ci:
                without_ci += 1
            if not has_tests:
                without_tests += 1
            if is_stale:
                stale += 1
            if has_readme and has_ci and has_tests and not is_stale:
                healthy += 1

        return WorkspaceHealth(
            total_projects=len(project_paths),
            healthy_projects=healthy,
            projects_without_readme=without_readme,
            projects_without_ci=without_ci,
            projects_without_tests=without_tests,
            stale_projects=stale,
        )

    def save_workspace_context(self, summary: WorkspaceSummary) -> Path:
        path = self.workspace_context_path(self._root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(summary.to_json(), encoding="utf-8")
        ensure_smith_gitignore_entry(self._root)
        logger.info("Saved workspace context to %s", path)
        return path

    def load_workspace_context(self) -> WorkspaceSummary | None:
        path = self.workspace_context_path(self._root)
        if not path.is_file():
            return None
        try:
            return WorkspaceSummary.from_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, KeyError) as exc:
            logger.warning("Failed to load workspace context from %s: %s", path, exc)
            return None

    def _build_workspace_project(self, project_path: Path) -> WorkspaceProject:
        context, _ = self._context_service.build(project_path)
        lang = display_language(context.language)
        framework = display_framework(context.framework)
        build = display_build(context.build_system)

        git_status = try_get_repository_status(project_path)
        last_commit_date = try_get_last_commit_date(project_path)
        last_activity = format_last_activity(last_commit_date)

        branch = None
        modified_files = 0
        staged_files = 0
        status = ProjectStatus.UNKNOWN
        activity_score = 0

        if git_status is not None:
            branch = git_status.branch
            modified_files = (
                git_status.modified + git_status.added + git_status.untracked + git_status.deleted
            )
            staged_files = git_status.staged
            status = _derive_project_status(modified_files, last_commit_date)
            activity_score = compute_activity_score(
                modified_files=modified_files,
                staged_files=staged_files,
                last_commit_date=last_commit_date,
            )

        return WorkspaceProject(
            name=project_path.name,
            path=str(project_path),
            language=lang,
            framework=framework,
            build_system=build,
            branch=branch,
            last_commit_date=last_commit_date,
            last_activity=last_activity,
            modified_files=modified_files,
            status=status,
            activity_score=activity_score,
        )


def _is_project_directory(directory: Path) -> bool:
    if (directory / ".git").is_dir():
        return True
    return any((directory / marker).is_file() for marker in PROJECT_FILE_MARKERS)


def _parse_commit_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def format_last_activity(last_commit_date: str | None) -> str:
    commit_dt = _parse_commit_datetime(last_commit_date)
    if commit_dt is None:
        return "Unknown"

    now = datetime.now(UTC)
    if commit_dt.tzinfo is None:
        commit_dt = commit_dt.replace(tzinfo=UTC)

    delta = now.date() - commit_dt.date()
    days = delta.days

    if days <= 0:
        return "Today"
    if days == 1:
        return "Yesterday"
    if days < 7:
        return f"{days} days ago"
    if days < 30:
        weeks = days // 7
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    months = days // 30
    if months < 12:
        return f"{months} month{'s' if months != 1 else ''} ago"
    years = days // 365
    return f"{years} year{'s' if years != 1 else ''} ago"


def compute_activity_score(
    *,
    modified_files: int,
    staged_files: int,
    last_commit_date: str | None,
) -> int:
    commit_dt = _parse_commit_datetime(last_commit_date)
    recent_bonus = 0
    if commit_dt is not None:
        now = datetime.now(UTC)
        if commit_dt.tzinfo is None:
            commit_dt = commit_dt.replace(tzinfo=UTC)
        age = now - commit_dt
        if age <= timedelta(days=7):
            recent_bonus = 10
        elif age <= timedelta(days=30):
            recent_bonus = 5
    return (modified_files * 3) + (staged_files * 5) + recent_bonus


def _derive_project_status(modified_files: int, last_commit_date: str | None) -> str:
    if modified_files > 0:
        return ProjectStatus.ACTIVE
    commit_dt = _parse_commit_datetime(last_commit_date)
    if commit_dt is not None:
        now = datetime.now(UTC)
        if commit_dt.tzinfo is None:
            commit_dt = commit_dt.replace(tzinfo=UTC)
        if now - commit_dt <= timedelta(days=30):
            return ProjectStatus.ACTIVE
        return ProjectStatus.IDLE
    return ProjectStatus.UNKNOWN


def _is_stale_project(project_path: Path, last_commit_date: str | None) -> bool:
    if try_get_last_commit_date(project_path) is None and last_commit_date is None:
        return False
    commit_dt = _parse_commit_datetime(last_commit_date)
    if commit_dt is None:
        return False
    now = datetime.now(UTC)
    if commit_dt.tzinfo is None:
        commit_dt = commit_dt.replace(tzinfo=UTC)
    return now - commit_dt > timedelta(days=90)


def _has_readme(project_path: Path) -> bool:
    return any((project_path / name).is_file() for name in README_NAMES)


def _has_ci(project_path: Path) -> bool:
    return (project_path / ".github" / "workflows").is_dir() or (
        project_path / ".gitlab-ci.yml"
    ).is_file()


def _has_tests(project_path: Path) -> bool:
    return any((project_path / d).exists() for d in ("tests", "test", "src/test"))


def format_workspace_summary(summary: WorkspaceSummary) -> str:
    lines = [
        "Workspace Summary",
        "",
        f"Root: {summary.root}",
        f"Projects: {summary.project_count}",
        "",
    ]
    if summary.warnings:
        lines.append("Warnings:")
        for warning in summary.warnings:
            lines.append(f"  - {warning}")
        lines.append("")
    if summary.languages:
        lines.append("Languages:")
        for lang, count in summary.languages.items():
            lines.append(f"  {lang}: {count}")
        lines.append("")
    lines.append("Projects:")
    for project in summary.projects[:15]:
        lines.append(
            f"  {project.name} | {project.language or '—'} | "
            f"{project.framework or '—'} | {project.status} | {project.last_activity}"
        )
    return "\n".join(lines)


def format_workspace_health(health: WorkspaceHealth) -> str:
    return "\n".join(
        [
            "Workspace Health",
            "",
            f"Total Projects: {health.total_projects}",
            f"Healthy Projects: {health.healthy_projects}",
            f"Missing README: {health.projects_without_readme}",
            f"Missing CI: {health.projects_without_ci}",
            f"Missing Tests: {health.projects_without_tests}",
            f"Stale Projects: {health.stale_projects}",
        ]
    )


def render_workspace_summary(summary: WorkspaceSummary, console) -> None:
    from rich.markup import escape
    from rich.panel import Panel
    from rich.table import Table

    console.print("[bold]Workspace Summary[/bold]\n")

    if summary.warnings:
        console.print(
            Panel(
                "\n".join(escape(w) for w in summary.warnings),
                title="Warnings",
                border_style="yellow",
                expand=False,
            )
        )
        console.print()

    table = Table(title="Projects", show_header=True, header_style="bold")
    table.add_column("Project")
    table.add_column("Lang")
    table.add_column("Framework")
    table.add_column("Status")
    table.add_column("Last Activity")
    for project in summary.projects:
        table.add_row(
            project.name,
            project.language or "—",
            project.framework or "—",
            project.status,
            project.last_activity,
        )
    console.print(table)
    console.print()

    if summary.languages:
        lang_table = Table(title="Languages", show_header=True, header_style="bold")
        lang_table.add_column("Language")
        lang_table.add_column("Count")
        for lang, count in sorted(summary.languages.items(), key=lambda x: -x[1]):
            lang_table.add_row(lang, str(count))
        console.print(lang_table)
        console.print()

    if summary.frameworks:
        fw_table = Table(title="Frameworks", show_header=True, header_style="bold")
        fw_table.add_column("Framework")
        fw_table.add_column("Count")
        for fw, count in sorted(summary.frameworks.items(), key=lambda x: -x[1]):
            fw_table.add_row(fw, str(count))
        console.print(fw_table)
        console.print()

    if summary.active_projects:
        active = summary.projects[:5]
        lines = [
            f"• {p.name} ({p.last_activity})" for p in active if p.name in summary.active_projects
        ]
        if not lines:
            lines = [f"• {p.name} ({p.last_activity})" for p in summary.projects[:5]]
        console.print(
            Panel(
                "\n".join(escape(ln) for ln in lines),
                title="Most Active Projects",
                border_style="cyan",
                expand=False,
            )
        )


def render_workspace_health(health: WorkspaceHealth, console) -> None:
    from rich.table import Table

    console.print("[bold]Workspace Health[/bold]\n")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Metric")
    table.add_column("Count")
    table.add_row("Total Projects", str(health.total_projects))
    table.add_row("Healthy Projects", str(health.healthy_projects))
    table.add_row("Missing README", str(health.projects_without_readme))
    table.add_row("Missing CI", str(health.projects_without_ci))
    table.add_row("Missing Tests", str(health.projects_without_tests))
    table.add_row("Stale Projects", str(health.stale_projects))
    console.print(table)
