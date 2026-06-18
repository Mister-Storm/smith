from pathlib import Path

import typer

from smith.cli.render import render_tool_result
from smith.services.tool_runner import run_duplicates


def duplicates(
    ctx: typer.Context,
    path: Path = typer.Argument(..., help="Directory to scan for duplicates"),
    min_size: int = typer.Option(0, "--min-size", help="Minimum file size in bytes"),
) -> None:
    """Find duplicate files in a directory."""
    result = run_duplicates(path, min_size=min_size)
    render_tool_result(result, tool_name="duplicates")
