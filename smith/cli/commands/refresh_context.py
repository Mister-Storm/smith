from pathlib import Path

import typer

from smith.cli.console import get_console, print_footer
from smith.core.formatting import format_result_footer
from smith.services.project_context import ProjectContextService, render_context_tables
from smith.services.tool_runner import run_refresh_context


def refresh_context(
    ctx: typer.Context,
    path: Path = typer.Argument(..., help="Project directory to re-analyze"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Export context as JSON"),
) -> None:
    """Force a full re-analysis and overwrite stored project context.

    Examples:

        smith refresh-context .
        smith refresh-context . --output context.json
    """
    result = run_refresh_context(path)
    if not result.success:
        typer.echo(result.message, err=True)
        raise typer.Exit(code=1)

    from smith.models.project_context import ProjectContext

    context_data = ProjectContext.from_dict(result.metadata["context"])
    console = get_console()
    render_context_tables(context_data, console)

    if output:
        output.write_text(context_data.to_json(), encoding="utf-8")
        console.print(f"\nExported to {output}")

    stored = ProjectContextService.context_path(path)
    console.print(f"\nStored at {stored}")
    print_footer(format_result_footer("context", max(result.execution_time_ms, 0)))
