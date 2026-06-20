import typer

from smith.core.config import (
    DEFAULT_DEEPSEEK_MODEL,
    Config,
    format_deepseek_model_menu,
    normalize_deepseek_model,
    resolve_deepseek_model_choice,
    resolve_provider,
)
from smith.core.exceptions import ConfigurationError


def _display_path(path) -> str:
    from pathlib import Path

    home = Path.home()
    try:
        return f"~/{path.relative_to(home)}"
    except ValueError:
        return str(path)


def run_model_selection(*, choice: str | None = None) -> Config:
    config = Config.load()
    try:
        provider = resolve_provider(config)
    except ConfigurationError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

    if provider != "deepseek":
        typer.echo("Model selection is only available for the DeepSeek provider.")
        typer.echo("Set SMITH_LLM_PROVIDER=deepseek or configure DEEPSEEK_API_KEY.")
        raise typer.Exit(code=1)

    current = normalize_deepseek_model(config.deepseek_model)
    if choice is None:
        typer.echo(format_deepseek_model_menu())
        default = "1" if current == DEFAULT_DEEPSEEK_MODEL else "2"
        choice = typer.prompt("Select model (1/2, flash/pro, or full id)", default=default)

    config.deepseek_model = resolve_deepseek_model_choice(choice)
    config.save()
    typer.echo(f"\nDeepSeek model set to {config.deepseek_model}")
    typer.echo(f"Saved to {_display_path(config.config_file_path)}")
    return Config.load()


def model(
    ctx: typer.Context,
    choice: str | None = typer.Argument(
        None,
        help="deepseek-v4-flash, deepseek-v4-pro, flash, or pro",
    ),
) -> None:
    """Choose the DeepSeek V4 model (Flash or Pro).

    Examples:

        smith model

        smith model flash

        smith model deepseek-v4-pro
    """
    run_model_selection(choice=choice)
