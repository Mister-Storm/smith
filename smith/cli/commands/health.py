from pathlib import Path

import typer

from smith.cli.console import get_console, print_footer
from smith.core.formatting import format_result_footer
from smith.models.workstation_health import WorkstationHealthReport
from smith.services.tool_runner import run_workstation_health
from smith.services.workstation_health import render_workstation_health


def health(
    ctx: typer.Context,
    paths: list[Path] | None = typer.Option(
        None,
        "--paths",
        help="Directories to scan (default: Downloads, Desktop, Documents, CWD project)",
    ),
    stale_days: int = typer.Option(90, "--stale-days", help="Days before a file is stale"),
    min_size_mb: int = typer.Option(50, "--min-size-mb", help="Large file threshold in MB"),
    as_json: bool = typer.Option(False, "--json", help="Output report as JSON"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Export report to file"),
) -> None:
    """Scan workstation hygiene and produce safe, read-only recommendations.

    Unlike `smith doctor` (Smith installation checks), this scans workspace
    directories for clutter, caches, and project manifest issues.

    Examples:

        smith health
        smith health --paths ~/Downloads ~/Desktop
        smith health --json
        smith health -o health-report.json
    """
    path_strs = [str(p) for p in paths] if paths else None
    result = run_workstation_health(
        paths=path_strs,
        stale_days=stale_days,
        min_size_mb=min_size_mb,
        as_json=as_json,
    )
    if not result.success:
        typer.echo(result.message, err=True)
        raise typer.Exit(code=1)

    console = get_console()
    if as_json:
        console.print(result.message)
    else:
        report = WorkstationHealthReport.from_dict(result.metadata["report"])
        render_workstation_health(report, console)
        from smith.services.workstation_health import save_workstation_health_cache

        save_workstation_health_cache(Path.cwd(), report)

    if output:
        output.write_text(result.message, encoding="utf-8")
        console.print(f"\nExported to {output}")

    exit_code = result.metadata.get("exit_code", 0)
    print_footer(format_result_footer("health", max(result.execution_time_ms, 0)))
    raise typer.Exit(code=exit_code)
