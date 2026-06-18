from pathlib import Path

import typer

from smith.core.config import Config
from smith.core.exceptions import ConfigurationError
from smith.llm.factory import get_llm_provider
from smith.tools.summarize_pdf import SummarizePdfTool


def summarize(
    ctx: typer.Context,
    pdf: Path = typer.Argument(..., help="PDF file to summarize"),
    study_notes: bool = typer.Option(False, "--study-notes", help="Include study notes"),
) -> None:
    """Summarize a PDF document."""
    config = Config.load()
    try:
        llm = get_llm_provider(config)
    except ConfigurationError as exc:
        typer.echo(f"Configuration error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    tool = SummarizePdfTool(llm)
    result = tool.execute(path=str(pdf), study_notes=study_notes)

    if not result.success:
        typer.echo(result.output, err=True)
        raise typer.Exit(code=1)

    typer.echo(result.output)
