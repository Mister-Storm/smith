from __future__ import annotations

import shutil
import subprocess
import sys
from importlib import resources
from pathlib import Path

from rich.align import Align
from rich.columns import Columns
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

import smith
from smith.cli.console import get_console
from smith.core.config import Config, describe_provider_selection, get_active_model
from smith.memory.service import MemoryService

NEON = "rgb(0,255,102)"
GREEN = "rgb(0,168,68)"
MUTED = "grey50"
DIM = "grey35"

HEX_LOGO = r"""
       ╱╲
      ╱  ╲
     │ ◉──│──◉ │
     │  ╱ S ╲  │
     │ ◉──│──◉ │
      ╲  ╱
       ╲╱
"""


def _logo_path() -> Path:
    try:
        ref = resources.files("smith") / "assets" / "logo.png"
        with resources.as_file(ref) as path:
            return Path(path)
    except (FileNotFoundError, ModuleNotFoundError, TypeError):
        return Path(__file__).resolve().parents[1] / "assets" / "logo.png"


def _display_path(path) -> str:
    from pathlib import Path as PathLib

    home = PathLib.home()
    try:
        return f"~/{path.relative_to(home)}"
    except ValueError:
        return str(path)


def _styled_line(line: str) -> Text:
    text = Text()
    for char in line:
        if char in "╱╲│":
            text.append(char, style=GREEN)
        elif char in "◉─":
            text.append(char, style=NEON)
        elif char == "S":
            text.append(char, style=f"bold {NEON}")
        else:
            text.append(char)
    text.append("\n")
    return text


def _render_hex_logo() -> Text:
    art = Text()
    for line in HEX_LOGO.strip("\n").splitlines():
        art.append_text(_styled_line(line))
    return art


def _render_wordmark() -> Text:
    mark = Text()
    mark.append("S", style=f"bold {NEON}")
    mark.append("M", style=f"bold {NEON}")
    mark.append("I", style=f"bold {GREEN}")
    mark.append("T", style=f"bold {GREEN}")
    mark.append("H", style=f"bold {NEON}")
    mark.append("\n")
    mark.append("Open Source AI Operator", style=MUTED)
    return mark


def _try_print_logo_image(console) -> bool:
    if console.no_color or not sys.stdout.isatty():
        return False
    chafa = shutil.which("chafa")
    if chafa is None:
        return False
    logo = _logo_path()
    if not logo.is_file():
        return False
    try:
        result = subprocess.run(
            [
                chafa,
                "-s",
                "52x0",
                "--symbols",
                "block+border+space",
                "--colors",
                "256",
                str(logo),
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    output = result.stdout.strip()
    if not output:
        return False
    console.print(Align.center(Text(output)))
    return True


def _render_header(console) -> None:
    if not _try_print_logo_image(console):
        console.print(Align.center(_render_hex_logo()))
    console.print(Align.center(_render_wordmark()))


def _stat_chip(label: str, value: str) -> Text:
    chip = Text()
    chip.append(f"{label} ", style=DIM)
    chip.append(value, style=NEON)
    return chip


def _render_status_row(config: Config, memory: MemoryService) -> RenderableType:
    provider_name, _ = describe_provider_selection(config)
    model = get_active_model(config) or "—"
    conversation_count = memory.count_conversations()

    chips = [
        _stat_chip("version", smith.__version__),
        _stat_chip("provider", provider_name),
        _stat_chip("model", model),
        _stat_chip("sessions", str(conversation_count)),
    ]
    return Align.center(Columns(chips, padding=(0, 3)))


def _render_status_details(config: Config) -> RenderableType:
    details = Text()
    details.append("memory ", style=DIM)
    details.append(_display_path(config.db_path), style=MUTED)
    details.append("   config ", style=DIM)
    details.append(_display_path(config.config_file_path), style=MUTED)
    return Align.center(details)


def render_startup_banner(config: Config, memory: MemoryService) -> None:
    console = get_console()
    console.print()
    _render_header(console)
    console.print()
    console.print(Rule(style=GREEN))
    console.print(_render_status_row(config, memory))
    console.print(_render_status_details(config))
    console.print(Rule(style=GREEN))
    console.print()


def render_slash_commands_table() -> None:
    console = get_console()

    commands = [
        ("/context", "Show loaded project context"),
        ("/refresh-context", "Rebuild project context"),
        ("/duplicates <path>", "Find duplicate files"),
        ("/organize <path>", "Organize files (confirmation required)"),
        ("/analyze <path>", "Analyze a project"),
        ("/summarize <pdf>", "Summarize a PDF"),
        ("/health [path]", "Workstation hygiene scan (read-only)"),
        ("/git-summary", "Repository status and suggested commit"),
        ("/git-changes", "Explain current changes"),
        ("/commit-message", "Conventional Commit suggestions"),
        ("/release-notes", "Release notes from recent commits"),
        ("/git-health", "Compact repository health overview"),
        ("/workspace [path]", "Multi-project workspace overview"),
        ("/workspace-health [path]", "Workspace health across projects"),
        ("/workspace-context [path]", "Display cached workspace context"),
        ("/refresh-workspace-context [path]", "Cache workspace context"),
        ("/exit", "Quit chat session"),
    ]

    left = Table(show_header=False, box=None, padding=(0, 1), expand=True)
    left.add_column(style=f"bold {NEON}")
    left.add_column(style=MUTED)
    right = Table(show_header=False, box=None, padding=(0, 1), expand=True)
    right.add_column(style=f"bold {NEON}")
    right.add_column(style=MUTED)

    midpoint = (len(commands) + 1) // 2
    for cmd, desc in commands[:midpoint]:
        left.add_row(cmd, desc)
    for cmd, desc in commands[midpoint:]:
        right.add_row(cmd, desc)

    body = Group(
        Columns([left, right], equal=True, expand=True),
        Text(""),
        Align.center(
            Text.from_markup(
                f"[{MUTED}]Message Smith naturally, or run a slash command · "
                f"[{NEON}]/exit[/{NEON}] to quit[/{MUTED}]"
            )
        ),
    )
    console.print(
        Panel(
            body,
            title=f"[bold {NEON}]Commands[/bold {NEON}]",
            border_style=GREEN,
            padding=(1, 2),
            expand=False,
        )
    )
    console.print()
