import typer

from smith.cli.console import get_console
from smith.services.doctor import render_doctor_report, run_doctor


def doctor(
    ctx: typer.Context,
    test_provider: bool = typer.Option(False, "--test-provider", help="Test LLM connectivity"),
) -> None:
    """Run diagnostics on Smith installation and configuration.

    Examples:

        smith doctor
        smith doctor --test-provider
    """
    report = run_doctor(test_provider=test_provider)
    render_doctor_report(report, get_console())
    raise typer.Exit(code=report.exit_code)
