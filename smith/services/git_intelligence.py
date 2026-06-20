"""Read-only Git repository intelligence."""

from __future__ import annotations

import re
import subprocess
from collections import Counter
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

from smith.core.exceptions import GitNotRepositoryError
from smith.models.git_intelligence import (
    ChangeSummary,
    CommitSuggestion,
    DevelopmentAssessment,
    GitHealthReport,
    ReleaseNotes,
    RepositoryStatus,
)

# TODO(Sprint 7): Unified Status Dashboard — `smith status` will aggregate
# Workspace Summary, Project Context, Git Health (via get_git_health()),
# Workstation Health, Provider, and Memory.

_CONVENTIONAL_COMMIT_RE = re.compile(
    r"^(?P<type>\w+)(?:\((?P<scope>[^)]+)\))?(?P<breaking>!)?:\s*(?P<subject>.+)$"
)

_SMITH_INTERNAL_PREFIXES = (
    ".smith/",
    ".smith/project_context.json",
    ".smith/history/",
    ".smith/cache/",
    ".smith/workspace_context.json",
)

_AREA_RULES: list[tuple[str, str]] = [
    ("smith/services/git_", "Git"),
    ("smith/services/project_context", "Context"),
    ("smith/services/workstation_health", "Health"),
    ("smith/services/", "Services"),
    ("smith/models/", "Models"),
    ("smith/tools/", "Tools"),
    ("smith/cli/", "CLI"),
    ("tests/", "Tests"),
    (".github/", "CI/CD"),
]

_DOC_EXTENSIONS = {".md", ".rst", ".txt"}
_CONFIG_FILES = {"pyproject.toml", "setup.cfg", "setup.py", "Makefile", "Dockerfile"}
_CHORE_PATH_PREFIXES = (".github/", ".gitignore", ".pre-commit-config.yaml")


def _run_git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _is_smith_internal(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized == ".smith" or normalized.startswith(".smith/"):
        return True
    return any(
        normalized.startswith(p) or normalized == p.rstrip("/") for p in _SMITH_INTERNAL_PREFIXES
    )


def _filter_smith_paths(paths: Iterable[str]) -> list[str]:
    return [p for p in paths if not _is_smith_internal(p)]


def _classify_area(path: str) -> str:
    normalized = path.replace("\\", "/").rstrip("/")
    if not normalized or normalized.endswith("/"):
        parts = PurePosixPath(normalized).parts
        if parts:
            normalized = "/".join(parts)
    for prefix, area in _AREA_RULES:
        if normalized.startswith(prefix) or normalized == prefix.rstrip("/"):
            return area
    parts = PurePosixPath(normalized).parts
    if len(parts) >= 2:
        return parts[-2].replace("_", " ").title()
    if parts:
        return parts[0].replace("_", " ").title()
    return "Other"


def _classify_areas(paths: list[str]) -> list[str]:
    if not paths:
        return []
    counts = Counter(_classify_area(p) for p in paths)
    return [area for area, _ in counts.most_common()]


def _scope_from_area(area: str) -> str:
    return area.lower().replace(" ", "-").replace("/", "-")


def _compute_assessment(
    *,
    modified: int,
    untracked: int,
    staged: int,
) -> DevelopmentAssessment:
    if modified == 0 and untracked == 0 and staged == 0:
        return DevelopmentAssessment.CLEAN
    if staged > 0 and modified <= 3:
        return DevelopmentAssessment.READY_FOR_COMMIT
    if staged == 0 and (modified > 3 or untracked > 3):
        return DevelopmentAssessment.WORK_IN_PROGRESS
    if staged > 0:
        return DevelopmentAssessment.READY_FOR_COMMIT
    return DevelopmentAssessment.WORK_IN_PROGRESS


def _parse_porcelain(lines: list[str]) -> dict[str, int]:
    counts = {
        "modified": 0,
        "added": 0,
        "deleted": 0,
        "renamed": 0,
        "untracked": 0,
        "staged": 0,
    }
    for line in lines:
        if not line.strip():
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if _is_smith_internal(path):
            continue

        x, y = line[0], line[1]
        if x == "?" and y == "?":
            counts["untracked"] += 1
            continue

        if x != " ":
            counts["staged"] += 1
        if x == "A":
            counts["added"] += 1
        elif x == "D":
            counts["deleted"] += 1
        elif x == "R":
            counts["renamed"] += 1
        elif x in ("M", "T") or y in ("M", "T"):
            counts["modified"] += 1
        elif y == "D":
            counts["deleted"] += 1

    return counts


class GitIntelligenceService:
    def __init__(self, cwd: Path | None = None) -> None:
        self._start_cwd = (cwd or Path.cwd()).resolve()
        self._repo_root = self._resolve_repo_root()

    def _resolve_repo_root(self) -> Path:
        result = _run_git(["rev-parse", "--show-toplevel"], cwd=self._start_cwd)
        if result.returncode != 0:
            raise GitNotRepositoryError("Current directory is not a Git repository.")
        return Path(result.stdout.strip()).resolve()

    def _git(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        return _run_git(args, cwd=self._repo_root)

    def _porcelain_lines(self) -> list[str]:
        result = self._git(["status", "--porcelain=v1", "-uall"])
        if result.returncode != 0:
            return []
        return [ln for ln in result.stdout.splitlines() if ln.strip()]

    def _current_branch(self) -> str:
        result = self._git(["branch", "--show-current"])
        if result.returncode != 0:
            return "unknown"
        branch = result.stdout.strip()
        return branch or "HEAD (detached)"

    def _changed_file_paths(self) -> list[str]:
        unstaged = self._git(["diff", "--name-only"])
        staged = self._git(["diff", "--cached", "--name-only"])
        paths: list[str] = []
        if unstaged.returncode == 0:
            paths.extend(unstaged.stdout.splitlines())
        if staged.returncode == 0:
            paths.extend(staged.stdout.splitlines())

        for line in self._porcelain_lines():
            if line.startswith("??"):
                path = line[3:]
                if " -> " in path:
                    path = path.split(" -> ", 1)[1]
                paths.append(path)

        seen: set[str] = set()
        unique: list[str] = []
        for p in paths:
            if p and p not in seen and not p.endswith("/"):
                seen.add(p)
                unique.append(p)
        return _filter_smith_paths(unique)

    def get_repository_status(self) -> RepositoryStatus:
        counts = _parse_porcelain(self._porcelain_lines())
        assessment = _compute_assessment(
            modified=counts["modified"],
            untracked=counts["untracked"],
            staged=counts["staged"],
        )
        is_clean = assessment == DevelopmentAssessment.CLEAN
        return RepositoryStatus(
            branch=self._current_branch(),
            modified=counts["modified"],
            added=counts["added"],
            deleted=counts["deleted"],
            renamed=counts["renamed"],
            untracked=counts["untracked"],
            staged=counts["staged"],
            is_clean=is_clean,
            repo_root=str(self._repo_root),
            assessment=assessment,
        )

    def get_last_commit_date(self) -> str | None:
        result = self._git(["log", "-1", "--format=%cI"])
        if result.returncode != 0 or not result.stdout.strip():
            return None
        return result.stdout.strip()

    def get_git_health(self) -> GitHealthReport:
        status = self.get_repository_status()
        paths = self._changed_file_paths()
        areas = _classify_areas(paths)
        largest_area = areas[0] if areas else None

        log_result = self._git(["log", "--since=7.days.ago", "--oneline"])
        recent = 0
        if log_result.returncode == 0 and log_result.stdout.strip():
            recent = len(log_result.stdout.strip().splitlines())

        return GitHealthReport(
            repo_name=self._repo_root.name,
            branch=status.branch,
            modified=status.modified,
            untracked=status.untracked,
            staged=status.staged,
            recent_commits_7d=recent,
            largest_area=largest_area,
            assessment=status.assessment,
        )

    def summarize_changes(self) -> ChangeSummary:
        paths = self._changed_file_paths()
        areas = _classify_areas(paths)
        summary_lines = _build_summary_lines(paths, areas)
        return ChangeSummary(
            files=paths,
            areas=areas,
            summary_lines=summary_lines,
            llm_summary=None,
        )

    def _untracked_paths(self) -> set[str]:
        untracked: set[str] = set()
        for line in self._porcelain_lines():
            if line.startswith("??"):
                path = line[3:]
                if " -> " in path:
                    path = path.split(" -> ", 1)[1]
                if not _is_smith_internal(path):
                    untracked.add(path)
        return untracked

    def suggest_commit_messages(self) -> list[CommitSuggestion]:
        paths = self._changed_file_paths()
        if not paths:
            return [
                CommitSuggestion(
                    message="chore: update project files",
                    type="chore",
                    scope="project",
                )
            ]
        return _build_commit_suggestions(paths, self._untracked_paths())

    def generate_release_notes(self, commit_count: int = 20) -> ReleaseNotes:
        result = self._git(["log", f"-n{commit_count}", "--pretty=format:%s"])
        subjects = []
        if result.returncode == 0:
            subjects = [s.strip() for s in result.stdout.splitlines() if s.strip()]
        return _bucket_release_notes(subjects)


def try_git_repo_root(cwd: Path) -> Path | None:
    result = _run_git(["rev-parse", "--show-toplevel"], cwd=cwd.resolve())
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip()).resolve()


def try_get_last_commit_date(cwd: Path) -> str | None:
    root = try_git_repo_root(cwd)
    if root is None:
        return None
    result = _run_git(["log", "-1", "--format=%cI"], cwd=root)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return result.stdout.strip()


def try_get_repository_status(cwd: Path) -> RepositoryStatus | None:
    try:
        return GitIntelligenceService(cwd=cwd).get_repository_status()
    except GitNotRepositoryError:
        return None


def _build_summary_lines(paths: list[str], areas: list[str]) -> list[str]:
    if not paths:
        return ["Working tree is clean."]

    lines: list[str] = []
    test_paths = [p for p in paths if p.startswith("tests/") or "/test_" in p]
    doc_paths = [p for p in paths if _is_doc_path(p)]

    if areas:
        top = areas[0]
        if top == "Git":
            lines.append("Updated Git intelligence and repository awareness.")
        elif top == "Health":
            lines.append("Refactored workstation health scoring and diagnostics.")
        elif top == "Context":
            lines.append("Improved project context detection and storage.")
        elif top == "Tests":
            lines.append("Updated test coverage and fixtures.")
        else:
            lines.append(f"Updated {top.lower()} components.")

    if len(test_paths) >= len(paths) // 2 and test_paths:
        lines.append("Expanded or revised test suite.")
    if doc_paths and len(doc_paths) >= len(paths) // 2:
        lines.append("Updated documentation.")
    if len(paths) > 5:
        lines.append(f"Touched {len(paths)} files across the repository.")
    elif len(paths) > 1:
        lines.append(f"Modified {len(paths)} files.")

    if not lines:
        lines.append("Made incremental changes to the codebase.")

    return lines[:4]


def _is_doc_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized.startswith("docs/"):
        return True
    return Path(path).suffix.lower() in _DOC_EXTENSIONS


def _is_config_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    name = PurePosixPath(normalized).name
    if name in _CONFIG_FILES:
        return True
    return any(normalized.startswith(p) for p in _CHORE_PATH_PREFIXES)


def _infer_commit_type(paths: list[str], untracked: set[str]) -> str:
    test_only = all(p.startswith("tests/") or "/test_" in p for p in paths)
    if test_only:
        return "test"
    doc_only = all(_is_doc_path(p) for p in paths)
    if doc_only:
        return "docs"
    config_only = all(_is_config_path(p) for p in paths)
    if config_only:
        return "chore"
    if any("perf" in p.lower() for p in paths):
        return "perf"
    if any("fix" in p.lower() for p in paths):
        return "fix"

    new_count = sum(1 for p in paths if p in untracked)
    if new_count > len(paths) // 2:
        return "feat"

    return "refactor"


def _build_description(paths: list[str], areas: list[str]) -> str:
    if areas:
        area = areas[0].lower()
        verbs = {
            "git": "add repository intelligence commands",
            "health": "improve workstation health diagnostics",
            "context": "improve project context detection",
            "tests": "expand test coverage",
            "cli": "update CLI commands",
            "models": "update data models",
            "services": "refactor service layer",
        }
        if area in verbs:
            return verbs[area]

    basenames = [PurePosixPath(p).stem.replace("_", " ") for p in paths[:3]]
    if basenames:
        return f"update {' and '.join(basenames)}"
    return "update project files"


def _build_commit_suggestions(paths: list[str], untracked: set[str]) -> list[CommitSuggestion]:
    areas = _classify_areas(paths)
    primary_type = _infer_commit_type(paths, untracked)
    scope = _scope_from_area(areas[0]) if areas else "project"
    description = _build_description(paths, areas)

    suggestions: list[CommitSuggestion] = []
    primary = CommitSuggestion(
        message=f"{primary_type}({scope}): {description}",
        type=primary_type,
        scope=scope,
    )
    suggestions.append(primary)

    alt_types = ["feat", "refactor", "fix", "test", "docs", "chore", "perf"]
    alt_types = [t for t in alt_types if t != primary_type]
    alt_scopes = [_scope_from_area(a) for a in areas[1:3]] or ["project", "core"]

    for alt_type, alt_scope in zip(alt_types, alt_scopes, strict=False):
        if len(suggestions) >= 3:
            break
        msg = f"{alt_type}({alt_scope}): {description}"
        if not any(s.message == msg for s in suggestions):
            suggestions.append(CommitSuggestion(message=msg, type=alt_type, scope=alt_scope))

    return suggestions[:3]


def _bucket_release_notes(subjects: list[str]) -> ReleaseNotes:
    notes = ReleaseNotes()
    for subject in subjects:
        match = _CONVENTIONAL_COMMIT_RE.match(subject)
        if match:
            commit_type = match.group("type").lower()
            text = match.group("subject").strip()
        else:
            notes.other.append(subject)
            continue

        if commit_type == "feat":
            notes.features.append(text)
        elif commit_type == "fix":
            notes.fixes.append(text)
        elif commit_type in ("refactor", "perf"):
            notes.improvements.append(text)
        elif commit_type == "docs":
            notes.documentation.append(text)
        elif commit_type == "test":
            notes.testing.append(text)
        elif commit_type == "chore":
            notes.maintenance.append(text)
        else:
            notes.other.append(subject)

    return notes


def format_git_summary(
    status: RepositoryStatus,
    suggestions: list[CommitSuggestion],
    *,
    areas: list[str] | None = None,
) -> str:
    lines = [
        f"Branch: {status.branch}",
        "",
        "Status:",
        f"  {status.modified} modified files",
        f"  {status.added} new files",
        f"  {status.deleted} deleted file(s)",
        f"  {status.untracked} untracked",
        f"  {status.staged} staged",
        "",
        f"Assessment: {status.assessment.label}",
    ]
    if areas:
        lines.extend(["", "Top Areas Changed:", ""])
        lines.extend(f"  * {a}" for a in areas[:5])
    if suggestions:
        lines.extend(["", "Suggested Commit:", "", f"  {suggestions[0].message}"])
    return "\n".join(lines)


def format_git_health(report: GitHealthReport) -> str:
    lines = [
        "Git Health",
        "",
        f"Repository: {report.repo_name}",
        f"Branch: {report.branch}",
        f"Modified: {report.modified}",
        f"Untracked: {report.untracked}",
        f"Staged: {report.staged}",
        f"Recent Activity: {report.recent_commits_7d} commits in last 7 days",
    ]
    if report.largest_area:
        lines.append(f"Largest Area: {report.largest_area}")
    lines.append(f"Assessment: {report.assessment.label}")
    return "\n".join(lines)


def format_git_changes(summary: ChangeSummary) -> str:
    lines = ["Files Changed:", ""]
    if summary.files:
        lines.extend(summary.files[:20])
        if len(summary.files) > 20:
            lines.append(f"... and {len(summary.files) - 20} more")
    else:
        lines.append("(none)")
    lines.extend(["", "Summary:", ""])
    lines.extend(summary.summary_lines)
    return "\n".join(lines)


def format_commit_suggestions(suggestions: list[CommitSuggestion]) -> str:
    lines = ["Suggested Commits:", ""]
    for suggestion in suggestions:
        lines.append(suggestion.message)
        lines.append("")
    return "\n".join(lines).rstrip()


def format_release_notes(notes: ReleaseNotes) -> str:
    lines = ["Release Notes", ""]
    sections = [
        ("Features", notes.features),
        ("Improvements", notes.improvements),
        ("Bug Fixes", notes.fixes),
        ("Documentation", notes.documentation),
        ("Testing", notes.testing),
        ("Maintenance", notes.maintenance),
        ("Other", notes.other),
    ]
    for title, items in sections:
        if not items:
            continue
        lines.append(title)
        lines.append("")
        lines.extend(f"  * {item}" for item in items)
        lines.append("")
    return "\n".join(lines).rstrip()


def render_git_summary(
    status: RepositoryStatus,
    suggestions: list[CommitSuggestion],
    areas: list[str],
    console,
) -> None:
    from rich.markup import escape
    from rich.panel import Panel
    from rich.table import Table

    console.print("[bold]Git Summary[/bold]\n")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Branch", status.branch)
    table.add_row("Modified", str(status.modified))
    table.add_row("Added", str(status.added))
    table.add_row("Deleted", str(status.deleted))
    table.add_row("Untracked", str(status.untracked))
    table.add_row("Staged", str(status.staged))
    table.add_row("Assessment", status.assessment.label)
    console.print(table)
    console.print()

    if areas:
        console.print("[bold]Top Areas Changed[/bold]")
        for area in areas[:5]:
            console.print(f"  • {area}")
        console.print()

    if suggestions:
        console.print(
            Panel(
                escape(suggestions[0].message),
                title="Suggested Commit",
                border_style="cyan",
                expand=False,
            )
        )


def render_git_health(report: GitHealthReport, console) -> None:
    from rich.table import Table

    console.print("[bold]Git Health[/bold]\n")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Repository", report.repo_name)
    table.add_row("Branch", report.branch)
    table.add_row("Modified", str(report.modified))
    table.add_row("Untracked", str(report.untracked))
    table.add_row("Staged", str(report.staged))
    table.add_row("Recent Activity", f"{report.recent_commits_7d} commits in last 7 days")
    if report.largest_area:
        table.add_row("Largest Area", report.largest_area)
    table.add_row("Assessment", report.assessment.label)
    console.print(table)


def render_git_changes(summary: ChangeSummary, console) -> None:
    from rich.markup import escape
    from rich.panel import Panel

    console.print("[bold]Git Changes[/bold]\n")

    if summary.files:
        file_lines = summary.files[:25]
        if len(summary.files) > 25:
            file_lines.append(f"... and {len(summary.files) - 25} more")
        console.print("[bold]Files Changed[/bold]")
        for f in file_lines:
            console.print(f"  {f}")
        console.print()

    body = "\n".join(escape(ln) for ln in summary.summary_lines)
    console.print(Panel(body, title="Summary", border_style="blue", expand=False))


def render_commit_suggestions(suggestions: list[CommitSuggestion], console) -> None:
    from rich.markup import escape
    from rich.panel import Panel

    console.print("[bold]Suggested Commits[/bold]\n")
    for i, suggestion in enumerate(suggestions, 1):
        console.print(
            Panel(
                escape(suggestion.message),
                title=f"Option {i}",
                border_style="cyan",
                expand=False,
            )
        )
        console.print()


def render_release_notes(notes: ReleaseNotes, console) -> None:
    console.print("[bold]Release Notes[/bold]\n")
    sections = [
        ("Features", notes.features),
        ("Improvements", notes.improvements),
        ("Bug Fixes", notes.fixes),
        ("Documentation", notes.documentation),
        ("Testing", notes.testing),
        ("Maintenance", notes.maintenance),
        ("Other", notes.other),
    ]
    for title, items in sections:
        if not items:
            continue
        console.print(f"[bold]{title}[/bold]")
        for item in items:
            console.print(f"  • {item}")
        console.print()
