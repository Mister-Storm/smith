from pathlib import Path

import typer

from smith.cli.render import render_tool_result
from smith.core.config import Config
from smith.services.tool_runner import run_context


def context(
    ctx: typer.Context,
    path: Path = typer.Argument(..., help="Project directory to inspect"),
) -> None:
    """Generate and persist structured project context."""
    config = Config.load()
    result = run_context(path, config=config, save=True)
    render_tool_result(result, tool_name="context")
