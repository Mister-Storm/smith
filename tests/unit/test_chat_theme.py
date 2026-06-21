from smith.cli.thinking_renderer import ThinkingRenderer
from smith.core.config import UIConfig


def test_renderer_warning_and_error(capsys):
    ui = UIConfig(error_color="red", thinking_color="yellow")
    renderer = ThinkingRenderer(enabled=True, ui=ui)
    renderer.warning("partial evidence")
    renderer.error("failed to read")
    out = capsys.readouterr().out
    assert "partial evidence" in out
    assert "failed to read" in out
