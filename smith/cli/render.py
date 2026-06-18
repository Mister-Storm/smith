import typer

from smith.core.formatting import format_completion_line
from smith.tools.base import ToolResult


def render_tool_result(result: ToolResult, *, tool_name: str) -> None:
    if not result.success:
        typer.echo(result.message, err=True)
        raise typer.Exit(code=1)

    typer.echo(result.message)
    if result.output_path:
        typer.echo(f"Report written to {result.output_path}")
    if result.success:
        typer.echo(format_completion_line(tool_name, max(result.execution_time_ms, 0)))
