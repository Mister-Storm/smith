import time
from pathlib import Path

import typer

from smith.cli.console import get_console, print_footer
from smith.core.formatting import format_result_footer
from smith.services.status_dashboard import (
    StatusDashboardService,
    render_status_dashboard,
)


def status(
    ctx: typer.Context,
    path: Path | None = typer.Argument(None, help="Working directory (default: CWD)"),
) -> None:
    """Show a unified workstation status overview from cached context.

    Aggregates environment, project context, workspace summary, git status,
    and cached workstation health. Does not rescan or call AI.

    Examples:

        smith status
        smith status ~/development
    """
    started = time.perf_counter()
    cwd = path.resolve() if path else Path.cwd()
    report = StatusDashboardService(cwd).build_report()
    render_status_dashboard(report, get_console())
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    print_footer(format_result_footer("status", elapsed_ms))
