from pathlib import Path

import typer

from smith.cli.render import render_tool_result
from smith.core.config import Config
from smith.core.exceptions import ConfigurationError
from smith.llm.factory import get_llm_provider
from smith.services.tool_runner import run_analyze


def analyze(
    ctx: typer.Context,
    path: Path = typer.Argument(..., help="Project directory to analyze"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write report to file"),
    structure_only: bool = typer.Option(
        False, "--structure-only", help="Structure report only, no LLM call"
    ),
) -> None:
    """Analyze a project and generate a markdown architecture report."""
    config = Config.load()
    llm = None
    if not structure_only:
        try:
            llm = get_llm_provider(config)
        except ConfigurationError as exc:
            typer.echo(f"Configuration error: {exc}", err=True)
            raise typer.Exit(code=1) from exc

    result = run_analyze(
        path,
        llm,
        output=output,
        structure_only=structure_only,
    )
    render_tool_result(result, tool_name="analyze")
