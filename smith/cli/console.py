import os
import sys

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

_console: Console | None = None


def _color_enabled() -> bool:
    if os.environ.get("SMITH_NO_COLOR") or os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def get_console() -> Console:
    global _console
    if _console is None:
        _console = Console(no_color=not _color_enabled(), highlight=False)
    return _console


def set_console(console: Console) -> None:
    global _console
    _console = console


def looks_like_markdown(text: str) -> bool:
    stripped = text.lstrip()
    return stripped.startswith("#") or stripped.startswith("## ") or "\n## " in text


def print_markdown(text: str) -> None:
    if looks_like_markdown(text):
        get_console().print(Markdown(text))
    else:
        get_console().print(text)


def print_panel(title: str, body: str, *, style: str = "blue") -> None:
    get_console().print(Panel(body, title=title, border_style=style, expand=False))


def print_error(message: str) -> None:
    get_console().print(Panel(message, title="Error", border_style="red", expand=False))


def print_footer(footer: str) -> None:
    get_console().print()
    get_console().print(footer, style="dim" if _color_enabled() else None)


def styled_prompt_label(label: str, color: str) -> str:
    if not _color_enabled():
        return label
    return f"[{color}]{label}[/{color}]"


def print_assistant_header(label: str = "Smith:", *, color: str = "bright_cyan") -> None:
    get_console().print(styled_prompt_label(label, color))
