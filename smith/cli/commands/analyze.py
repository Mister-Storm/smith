from pathlib import Path

import typer

from smith.core.config import Config
from smith.core.exceptions import ConfigurationError
from smith.llm.factory import get_llm_provider
from smith.tools.analyze_project import AnalyzeProjectTool


def analyze(
    ctx: typer.Context,
    path: Path = typer.Argument(..., help="Project directory to analyze"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write report to file"),
) -> None:
    """Analyze a project and generate a markdown architecture report."""
    config = Config.load()
    try:
        llm = get_llm_provider(config)
    except ConfigurationError as exc:
        typer.echo(f"Configuration error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    tool = AnalyzeProjectTool(llm)
    result = tool.execute(path=str(path))

    if not result.success:
        typer.echo(result.output, err=True)
        raise typer.Exit(code=1)

    if output:
        output.write_text(result.output, encoding="utf-8")
        typer.echo(f"Report written to {output}")
    else:
        typer.echo(result.output)
