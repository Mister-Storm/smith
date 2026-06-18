from smith.core.formatting import (
    CONFIG_REQUIRED_MSG,
    format_completion_line,
    format_duration_ms,
    format_execution_time,
    format_llm_line,
    format_result_footer,
    get_next_action,
)


def test_format_duration_ms_seconds():
    assert format_duration_ms(1250) == "1.2 seconds"


def test_format_duration_ms_small():
    assert format_duration_ms(420) == "420 ms"


def test_format_completion_line():
    line = format_completion_line("analyze", 1250)
    assert line == "Analysis completed in 1.2 seconds."


def test_format_execution_time():
    assert format_execution_time(1800) == "1.8s"
    assert format_execution_time(420) == "420ms"


def test_format_result_footer():
    footer = format_result_footer("analyze", 1800)
    assert "✓ Analysis completed" in footer
    assert "Execution time: 1.8s" in footer
    assert "Next: smith context ." in footer


def test_format_result_footer_with_llm():
    footer = format_result_footer("summarize", 500, provider="OpenAI", model="gpt-4o-mini")
    assert "Provider: OpenAI · Model: gpt-4o-mini" in footer


def test_format_llm_line():
    assert format_llm_line("OpenAI", "gpt-4o-mini") == "Provider: OpenAI · Model: gpt-4o-mini"


def test_get_next_action():
    assert get_next_action("analyze") == "smith context ."
    assert get_next_action("unknown") is None


def test_config_required_msg():
    assert "smith setup" in CONFIG_REQUIRED_MSG
