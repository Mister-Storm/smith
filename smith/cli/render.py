import typer

from smith.cli.console import print_error, print_footer, print_markdown
from smith.core.formatting import format_result_footer
from smith.tools.base import ToolResult


def render_tool_result(
    result: ToolResult,
    *,
    tool_name: str,
    provider: str | None = None,
    model: str | None = None,
) -> None:
    if not result.success:
        print_error(result.message)
        raise typer.Exit(code=1)

    print_markdown(result.message)
    if result.output_path:
        print_markdown(f"Report written to `{result.output_path}`")

    footer = format_result_footer(
        tool_name,
        max(result.execution_time_ms, 0),
        provider=provider,
        model=model,
    )
    print_footer(footer)
