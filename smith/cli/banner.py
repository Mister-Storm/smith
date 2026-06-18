from rich.panel import Panel
from rich.table import Table

import smith
from smith.cli.console import get_console
from smith.core.config import Config, describe_provider_selection, get_active_model
from smith.memory.service import MemoryService


def _display_path(path) -> str:
    from pathlib import Path

    home = Path.home()
    try:
        return f"~/{path.relative_to(home)}"
    except ValueError:
        return str(path)


def render_startup_banner(config: Config, memory: MemoryService) -> None:
    provider_name, _ = describe_provider_selection(config)
    model = get_active_model(config) or "—"
    conversation_count = memory.count_conversations()

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row("Version", smith.__version__)
    table.add_row("Provider", provider_name)
    table.add_row("Model", model)
    table.add_row("Memory", _display_path(config.db_path))
    table.add_row("Conversations", str(conversation_count))
    table.add_row("Config", _display_path(config.config_file_path))

    panel = Panel(
        table,
        title="[bold]Smith[/bold]",
        subtitle="A benevolent personal AI operator",
        border_style="blue",
        expand=False,
    )
    get_console().print(panel)


def render_slash_commands_table() -> None:
    table = Table(title="Slash Commands", show_header=True, header_style="bold")
    table.add_column("Command", style="cyan")
    table.add_column("Description")

    commands = [
        ("/context <path>", "Generate project context snapshot"),
        ("/duplicates <path>", "Find duplicate files"),
        ("/organize <path>", "Organize files (asks for confirmation)"),
        ("/analyze <path>", "Analyze a project"),
        ("/summarize <pdf>", "Summarize a PDF"),
        ("/exit", "Quit chat session"),
    ]
    for cmd, desc in commands:
        table.add_row(cmd, desc)

    get_console().print(table)
    get_console().print("Type a message or use a slash command. /exit to quit.")
