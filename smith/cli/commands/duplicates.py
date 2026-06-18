from pathlib import Path

import typer

from smith.tools.duplicates import FindDuplicateFilesTool


def duplicates(
    ctx: typer.Context,
    path: Path = typer.Argument(..., help="Directory to scan for duplicates"),
    min_size: int = typer.Option(0, "--min-size", help="Minimum file size in bytes"),
) -> None:
    """Find duplicate files in a directory."""
    tool = FindDuplicateFilesTool()
    result = tool.execute(path=str(path), min_size=min_size)

    if not result.success:
        typer.echo(result.output, err=True)
        raise typer.Exit(code=1)

    typer.echo(result.output)
