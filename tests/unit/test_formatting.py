from smith.core.formatting import format_completion_line, format_duration_ms


def test_format_duration_ms_seconds():
    assert format_duration_ms(1250) == "1.2 seconds"


def test_format_duration_ms_small():
    assert format_duration_ms(420) == "420 ms"


def test_format_completion_line():
    line = format_completion_line("analyze", 1250)
    assert line == "Analysis completed in 1.2 seconds."
