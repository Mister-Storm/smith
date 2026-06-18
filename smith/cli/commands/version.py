import typer

import smith
from smith.cli.console import get_console
from smith.core.config import Config, describe_provider_selection, get_active_model, needs_setup


def version(ctx: typer.Context) -> None:
    """Show Smith version, active provider, and model.

    Examples:

        smith version
    """
    config = Config.load()
    console = get_console()

    if needs_setup(config):
        console.print(f"Smith {smith.__version__}")
        console.print("Provider: not configured")
        console.print("Run: smith setup")
        return

    provider_name, _ = describe_provider_selection(config)
    model = get_active_model(config) or "—"
    console.print(f"Smith {smith.__version__}")
    console.print(f"Provider: {provider_name}")
    console.print(f"Model: {model}")
