from pathlib import Path

import typer

from smith.cli.console import get_console, print_footer
from smith.core.exceptions import GitNotRepositoryError
from smith.core.formatting import format_result_footer
from smith.services.git_intelligence import (
    GitIntelligenceService,
    render_commit_suggestions,
    render_git_changes,
    render_git_health,
    render_git_summary,
    render_release_notes,
)

git_app = typer.Typer(
    help="Git repository intelligence (read-only — no commits, pushes, or mutations)",
    no_args_is_help=True,
)


def _service(path: Path | None) -> GitIntelligenceService:
    cwd = path.resolve() if path else Path.cwd()
    return GitIntelligenceService(cwd=cwd)


def _handle_git_error(exc: GitNotRepositoryError) -> None:
    typer.echo(str(exc), err=True)
    raise typer.Exit(code=1)


@git_app.command("summary")
def git_summary(
    ctx: typer.Context,
    path: Path | None = typer.Option(None, "--path", help="Repository path (default: CWD)"),
) -> None:
    """Summarize repository status, top changed areas, and a suggested commit.

    Examples:

        smith git summary
        smith git summary --path .
    """
    try:
        service = _service(path)
        status = service.get_repository_status()
        suggestions = service.suggest_commit_messages()
        areas = service.summarize_changes().areas
        render_git_summary(status, suggestions, areas, get_console())
    except GitNotRepositoryError as exc:
        _handle_git_error(exc)

    print_footer(format_result_footer("git summary", 0))


@git_app.command("changes")
def git_changes(
    ctx: typer.Context,
    path: Path | None = typer.Option(None, "--path", help="Repository path (default: CWD)"),
) -> None:
    """Explain current changes in human-readable form.

    Examples:

        smith git changes
    """
    try:
        service = _service(path)
        summary = service.summarize_changes()
        render_git_changes(summary, get_console())
    except GitNotRepositoryError as exc:
        _handle_git_error(exc)

    print_footer(format_result_footer("git changes", 0))


@git_app.command("commit-message")
def git_commit_message(
    ctx: typer.Context,
    path: Path | None = typer.Option(None, "--path", help="Repository path (default: CWD)"),
) -> None:
    """Suggest up to 3 Conventional Commit messages.

    Examples:

        smith git commit-message
    """
    try:
        service = _service(path)
        suggestions = service.suggest_commit_messages()
        render_commit_suggestions(suggestions, get_console())
    except GitNotRepositoryError as exc:
        _handle_git_error(exc)

    print_footer(format_result_footer("git commit-message", 0))


@git_app.command("release-notes")
def git_release_notes(
    ctx: typer.Context,
    path: Path | None = typer.Option(None, "--path", help="Repository path (default: CWD)"),
    commits: int = typer.Option(20, "--commits", help="Number of commits to include"),
) -> None:
    """Generate release notes from recent commit history.

    Examples:

        smith git release-notes
        smith git release-notes --commits 50
    """
    try:
        service = _service(path)
        notes = service.generate_release_notes(commit_count=commits)
        render_release_notes(notes, get_console())
    except GitNotRepositoryError as exc:
        _handle_git_error(exc)

    print_footer(format_result_footer("git release-notes", 0))


@git_app.command("health")
def git_health(
    ctx: typer.Context,
    path: Path | None = typer.Option(None, "--path", help="Repository path (default: CWD)"),
) -> None:
    """Compact repository health overview (Sprint 6 dashboard foundation).

    Examples:

        smith git health
    """
    try:
        service = _service(path)
        report = service.get_git_health()
        render_git_health(report, get_console())
    except GitNotRepositoryError as exc:
        _handle_git_error(exc)

    print_footer(format_result_footer("git health", 0))
