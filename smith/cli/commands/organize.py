from pathlib import Path

import typer

from smith.cli.console import print_footer, print_markdown
from smith.cli.render import render_tool_result
from smith.core.formatting import format_result_footer
from smith.services.tool_runner import run_organize


def organize(
    ctx: typer.Context,
    path: Path = typer.Argument(..., help="Directory to organize"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without moving files"),
) -> None:
    """Organize files in a directory into category folders.

    Examples:

        smith organize ~/Downloads --dry-run
        smith organize ~/Downloads
    """
    verbose_dry_run = ctx.obj.get("dry_run", False) if ctx.obj else False
    effective_dry_run = dry_run or verbose_dry_run

    preview = run_organize(path, dry_run=True)
    if not preview.success:
        typer.echo(preview.message, err=True)
        raise typer.Exit(code=1)

    print_markdown(preview.message)
    print_footer(format_result_footer("organize", max(preview.execution_time_ms, 0)))

    if effective_dry_run:
        return

    if not typer.confirm("Proceed with moving files?"):
        typer.echo("Organize cancelled.")
        return

    result = run_organize(path, dry_run=False)
    render_tool_result(result, tool_name="organize")
