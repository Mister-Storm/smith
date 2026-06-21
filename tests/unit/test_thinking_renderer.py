from smith.cli.thinking_renderer import ThinkingRenderer


def test_thinking_renderer_records_phases():
    renderer = ThinkingRenderer(enabled=False)
    renderer.phase("Thinking...")
    renderer.phase("Gathering context...")
    assert renderer.phases == ["Thinking...", "Gathering context..."]
