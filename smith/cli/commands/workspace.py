from pathlib import Path

import typer

from smith.cli.console import get_console, print_footer
from smith.core.exceptions import WorkspaceNoProjectsError
from smith.core.formatting import format_result_footer
from smith.services.workspace_intelligence import (
    WorkspaceIntelligenceService,
    render_workspace_health,
    render_workspace_summary,
)


def _service(path: Path | None, *, max_depth: int = 3) -> WorkspaceIntelligenceService:
    root = path.resolve() if path else Path.cwd()
    return WorkspaceIntelligenceService(root, max_depth=max_depth)


def workspace(
    ctx: typer.Context,
    path: Path | None = typer.Argument(None, help="Workspace directory (default: CWD)"),
    max_depth: int = typer.Option(3, "--max-depth", help="Maximum scan depth"),
) -> None:
    """Show a multi-project workspace overview.

    Examples:

        smith workspace ~/development
        smith workspace . --max-depth 2
    """
    try:
        service = _service(path, max_depth=max_depth)
        summary = service.build_workspace_summary()
        render_workspace_summary(summary, get_console())
    except WorkspaceNoProjectsError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    print_footer(format_result_footer("workspace", 0))


def workspace_health(
    ctx: typer.Context,
    path: Path | None = typer.Argument(None, help="Workspace directory (default: CWD)"),
    max_depth: int = typer.Option(3, "--max-depth", help="Maximum scan depth"),
) -> None:
    """Report workspace health across discovered projects.

    Examples:

        smith workspace-health ~/development
    """
    try:
        service = _service(path, max_depth=max_depth)
        health = service.build_workspace_health()
        render_workspace_health(health, get_console())
    except WorkspaceNoProjectsError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    print_footer(format_result_footer("workspace-health", 0))


def refresh_workspace_context(
    ctx: typer.Context,
    path: Path | None = typer.Argument(None, help="Workspace directory (default: CWD)"),
    max_depth: int = typer.Option(3, "--max-depth", help="Maximum scan depth"),
) -> None:
    """Generate and cache workspace context to .smith/workspace_context.json.

    Examples:

        smith refresh-workspace-context ~/development
    """
    console = get_console()
    try:
        service = _service(path, max_depth=max_depth)
        summary = service.build_workspace_summary()
        stored = service.save_workspace_context(summary)
        render_workspace_summary(summary, console)
        console.print(f"\nStored at {stored}")
    except WorkspaceNoProjectsError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    print_footer(format_result_footer("refresh-workspace-context", 0))


def workspace_context(
    ctx: typer.Context,
    path: Path | None = typer.Argument(None, help="Workspace directory (default: CWD)"),
) -> None:
    """Display cached workspace context.

    Examples:

        smith workspace-context
        smith workspace-context ~/development
    """
    console = get_console()
    service = _service(path)
    summary = service.load_workspace_context()
    if summary is None:
        typer.echo(
            "No workspace context found. Run `smith refresh-workspace-context` first.",
            err=True,
        )
        raise typer.Exit(code=1)

    render_workspace_summary(summary, console)
    print_footer(format_result_footer("workspace-context", 0))
