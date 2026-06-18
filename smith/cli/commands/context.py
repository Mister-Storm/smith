from pathlib import Path

import typer

from smith.cli.console import get_console, print_footer
from smith.core.formatting import format_result_footer
from smith.services.project_context import render_context_tables
from smith.services.tool_runner import run_context


def context(
    ctx: typer.Context,
    path: Path = typer.Argument(..., help="Project directory to inspect"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Export context as JSON"),
    debug: bool = typer.Option(False, "--debug", help="Show detection trace for troubleshooting"),
) -> None:
    """Inspect a project and save workspace context to .smith/project_context.json.

    Examples:

        smith context .
        smith context . --output context.json
        smith context . --debug
    """
    result = run_context(path, save=True, debug=debug)
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

    print_footer(format_result_footer("context", max(result.execution_time_ms, 0)))
