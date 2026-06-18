from pathlib import Path

import typer

from smith.cli.render import render_tool_result
from smith.core.config import Config, describe_provider_selection, get_active_model, needs_setup
from smith.core.exceptions import ConfigurationError
from smith.core.formatting import CONFIG_REQUIRED_MSG
from smith.llm.factory import get_llm_provider
from smith.services.tool_runner import run_analyze


def analyze(
    ctx: typer.Context,
    path: Path = typer.Argument(..., help="Project directory to analyze"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write report to file"),
    structure_only: bool = typer.Option(
        False, "--structure-only", help="Structure report only, no LLM call"
    ),
    as_json: bool = typer.Option(False, "--json", help="Output analysis as JSON"),
) -> None:
    """Analyze a project and generate a markdown architecture report.

    Examples:

        smith analyze .
        smith analyze . --structure-only
        smith analyze . --json
        smith analyze . -o report.md
    """
    config = Config.load()
    llm = None
    provider_name: str | None = None
    model: str | None = None

    if not structure_only and not as_json:
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

    result = run_analyze(
        path,
        llm,
        output=output,
        structure_only=structure_only,
        as_json=as_json,
    )
    if as_json:
        if not result.success:
            typer.echo(result.message, err=True)
            raise typer.Exit(code=1)
        typer.echo(result.message)
        return
    render_tool_result(result, tool_name="analyze", provider=provider_name, model=model)
