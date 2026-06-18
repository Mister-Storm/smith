from pathlib import Path

import typer

from smith.tools.organize import OrganizeDownloadsTool


def organize(
    ctx: typer.Context,
    path: Path = typer.Argument(..., help="Directory to organize"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without moving files"),
) -> None:
    """Organize files in a directory into category folders."""
    verbose_dry_run = ctx.obj.get("dry_run", False) if ctx.obj else False
    effective_dry_run = dry_run or verbose_dry_run

    tool = OrganizeDownloadsTool()
    preview = tool.execute(path=str(path), dry_run=True)

    if not preview.success:
        typer.echo(preview.output, err=True)
        raise typer.Exit(code=1)

    typer.echo(preview.output)

    if effective_dry_run:
        return

    if not typer.confirm("Proceed with moving files?"):
        typer.echo("Organize cancelled.")
        return

    result = tool.execute(path=str(path), dry_run=False)
    typer.echo(result.output)

    if not result.success:
        raise typer.Exit(code=1)
