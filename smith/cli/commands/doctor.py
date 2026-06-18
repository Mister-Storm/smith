import typer

from smith.services.doctor import format_doctor_report, run_doctor


def doctor(
    ctx: typer.Context,
    test_provider: bool = typer.Option(False, "--test-provider", help="Test LLM connectivity"),
) -> None:
    """Run diagnostics on Smith installation and configuration."""
    report = run_doctor(test_provider=test_provider)
    typer.echo(format_doctor_report(report))
    raise typer.Exit(code=report.exit_code)
