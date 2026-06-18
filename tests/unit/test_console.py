from io import StringIO

import pytest
from rich.console import Console

from smith.cli.console import looks_like_markdown, print_footer, print_markdown, set_console
from smith.core.formatting import format_result_footer


@pytest.fixture
def capture_console():
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=True, no_color=True, width=120)
    set_console(console)
    yield buffer
    set_console(None)


def test_looks_like_markdown():
    assert looks_like_markdown("# Title")
    assert looks_like_markdown("text\n## Section")
    assert not looks_like_markdown("plain text")


def test_print_markdown(capture_console):
    print_markdown("# Hello")
    assert "Hello" in capture_console.getvalue()


def test_print_footer(capture_console):
    print_footer(format_result_footer("context", 100))
    output = capture_console.getvalue()
    assert "✓ Context completed" in output
    assert "Execution time:" in output
