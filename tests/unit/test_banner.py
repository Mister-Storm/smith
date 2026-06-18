from io import StringIO

import pytest
from rich.console import Console

from smith.cli.banner import render_slash_commands_table, render_startup_banner
from smith.cli.console import set_console


@pytest.fixture
def capture_console():
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=True, no_color=True, width=120)
    set_console(console)
    yield buffer
    set_console(None)


def test_startup_banner(capture_console, config_with_openai, memory_service):
    render_startup_banner(config_with_openai, memory_service)
    output = capture_console.getvalue()
    assert "Smith" in output
    assert "OpenAI" in output
    assert "gpt-4o-mini" in output
    assert "Conversations" in output


def test_slash_commands_table(capture_console):
    render_slash_commands_table()
    output = capture_console.getvalue()
    assert "/context" in output
    assert "/analyze" in output
