import typer

from smith.cli.commands import analyze, chat, context, doctor, duplicates, organize, summarize
from smith.core.logging import setup_logging

app = typer.Typer(
    name="smith",
    help="Smith - a benevolent personal AI operator",
    no_args_is_help=True,
)


@app.callback()
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview destructive actions"),
) -> None:
    """Smith CLI."""
    setup_logging(verbose=verbose)
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["dry_run"] = dry_run


app.command()(chat.chat)
app.command()(context.context)
app.command()(analyze.analyze)
app.command()(duplicates.duplicates)
app.command()(organize.organize)
app.command()(summarize.summarize)
app.command()(doctor.doctor)

if __name__ == "__main__":
    app()
