import typer

from smith.services.setup_wizard import run_setup_wizard


def setup(ctx: typer.Context) -> None:
    """Configure Smith interactively (provider, API key env, memory database).

    Examples:

        smith setup
    """
    run_setup_wizard(configure_key=True)
