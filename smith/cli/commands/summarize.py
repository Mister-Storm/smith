from pathlib import Path

import typer

from smith.cli.render import render_tool_result
from smith.core.config import Config, describe_provider_selection, get_active_model, needs_setup
from smith.core.exceptions import ConfigurationError
from smith.core.formatting import CONFIG_REQUIRED_MSG
from smith.llm.factory import get_llm_provider
from smith.services.tool_runner import run_summarize


def summarize(
    ctx: typer.Context,
    pdf: Path = typer.Argument(..., help="PDF file to summarize"),
    study_notes: bool = typer.Option(False, "--study-notes", help="Include study notes"),
    pages: int | None = typer.Option(None, "--pages", help="Limit to first N pages"),
) -> None:
    """Summarize a PDF document.

    Examples:

        smith summarize document.pdf
        smith summarize document.pdf --study-notes
        smith summarize document.pdf --pages 10
    """
    config = Config.load()
    if needs_setup(config):
        typer.echo(CONFIG_REQUIRED_MSG, err=True)
        raise typer.Exit(code=1)
    try:
        llm = get_llm_provider(config)
        provider_name, _ = describe_provider_selection(config)
        model = get_active_model(config)
    except ConfigurationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    result = run_summarize(pdf, llm, study_notes=study_notes, pages=pages)
    render_tool_result(result, tool_name="summarize", provider=provider_name, model=model)
