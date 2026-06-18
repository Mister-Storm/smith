from pathlib import Path

import typer

from smith.cli.render import render_tool_result
from smith.core.config import Config
from smith.core.exceptions import ConfigurationError
from smith.llm.factory import get_llm_provider
from smith.services.tool_runner import run_summarize


def summarize(
    ctx: typer.Context,
    pdf: Path = typer.Argument(..., help="PDF file to summarize"),
    study_notes: bool = typer.Option(False, "--study-notes", help="Include study notes"),
    pages: int | None = typer.Option(None, "--pages", help="Limit to first N pages"),
) -> None:
    """Summarize a PDF document."""
    config = Config.load()
    try:
        llm = get_llm_provider(config)
    except ConfigurationError as exc:
        typer.echo(f"Configuration error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    result = run_summarize(pdf, llm, study_notes=study_notes, pages=pages)
    render_tool_result(result, tool_name="summarize")
