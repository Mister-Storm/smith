import typer
from rich.table import Table

from smith.cli.console import get_console, print_markdown

_COMMANDS = [
    ("chat", "Interactive chat session with slash commands"),
    ("setup", "Configure provider, API keys, and memory"),
    ("model", "Choose DeepSeek V4 model (Flash or Pro)"),
    ("version", "Show version, provider, and model"),
    ("context", "Inspect project and save .smith/project_context.json"),
    ("refresh-context", "Force re-analysis and overwrite project context"),
    ("analyze", "Analyze project architecture"),
    ("summarize", "Summarize a PDF document"),
    ("duplicates", "Find duplicate files by hash"),
    ("organize", "Organize files into category folders"),
    ("health", "Workstation hygiene scan (read-only recommendations)"),
    ("doctor", "Run installation diagnostics"),
    ("git summary", "Repository status and suggested commit (read-only)"),
    ("git changes", "Human-readable explanation of current changes"),
    ("git commit-message", "Conventional Commit message suggestions"),
    ("git release-notes", "Release notes from recent commits"),
    ("git health", "Compact repository health overview"),
    ("workspace", "Multi-project workspace overview"),
    ("workspace-health", "Workspace health across projects"),
    ("refresh-workspace-context", "Cache workspace context to .smith/"),
    ("workspace-context", "Display cached workspace context"),
]

_EXAMPLES = [
    ("Install", "pipx install smith-ai"),
    ("Setup", "smith setup"),
    ("DeepSeek model", "smith model flash"),
    ("Verify", "smith doctor"),
    ("Chat", "smith chat"),
    ("Version", "smith version"),
    ("Context", "smith context ."),
    ("Refresh Context", "smith refresh-context ."),
    ("Analyze", "smith analyze . --structure-only"),
    ("Analyze JSON", "smith analyze . --json"),
    ("Summarize", "smith summarize document.pdf --pages 10"),
    ("Duplicates", "smith duplicates ~/Downloads"),
    ("Organize", "smith organize ~/Downloads --dry-run"),
    ("Health", "smith health"),
    ("Health JSON", "smith health --json"),
    ("Git Summary", "smith git summary"),
    ("Git Changes", "smith git changes"),
    ("Git Health", "smith git health"),
    ("Commit Message", "smith git commit-message"),
    ("Release Notes", "smith git release-notes"),
    ("Workspace", "smith workspace ~/development"),
    ("Workspace Health", "smith workspace-health ~/development"),
    ("Refresh Workspace", "smith refresh-workspace-context ~/development"),
    ("Workspace Context", "smith workspace-context"),
]


def help_cmd(ctx: typer.Context) -> None:
    """Show Smith usage guide with examples for every command.

    Examples:

        smith help
    """
    console = get_console()

    print_markdown("# Smith — Usage Guide\n")
    print_markdown(
        "Smith is a personal AI operator CLI. API keys live in environment "
        "variables (never in config.toml).\n"
    )

    table = Table(title="Commands", show_header=True, header_style="bold")
    table.add_column("Command", style="cyan")
    table.add_column("Description")
    for name, desc in _COMMANDS:
        table.add_row(f"smith {name}", desc)
    console.print(table)
    console.print()

    examples = Table(title="Examples", show_header=True, header_style="bold")
    examples.add_column("Task")
    examples.add_column("Command", style="green")
    for task, cmd in _EXAMPLES:
        examples.add_row(task, cmd)
    console.print(examples)
