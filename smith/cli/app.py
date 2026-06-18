import typer

from smith.cli.commands import (
    analyze,
    chat,
    context,
    doctor,
    duplicates,
    organize,
    refresh_context,
    setup,
    summarize,
    version,
)
from smith.cli.commands import (
    help as help_cmd,
)
from smith.cli.console import get_console
from smith.core.logging import setup_logging

app = typer.Typer(
    name="smith",
    help="Smith - a benevolent personal AI operator",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@app.callback()
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview destructive actions"),
) -> None:
    """Smith CLI — your benevolent personal AI operator."""
    setup_logging(verbose=verbose)
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["dry_run"] = dry_run
    ctx.obj["console"] = get_console()


app.command()(chat.chat)
app.command()(setup.setup)
app.command()(version.version)
app.command(name="help")(help_cmd.help_cmd)
app.command()(context.context)
app.command(name="refresh-context")(refresh_context.refresh_context)
app.command()(analyze.analyze)
app.command()(duplicates.duplicates)
app.command()(organize.organize)
app.command()(summarize.summarize)
app.command()(doctor.doctor)

if __name__ == "__main__":
    app()
