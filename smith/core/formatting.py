def format_duration_ms(ms: int) -> str:
    if ms >= 1000:
        seconds = ms / 1000
        if seconds >= 10:
            return f"{seconds:.0f} seconds"
        return f"{seconds:.1f} seconds"
    return f"{ms} ms"


_TOOL_LABELS = {
    "analyze": "Analysis",
    "summarize": "Summarization",
    "duplicates": "Duplicate scan",
    "organize": "Organization",
}


def format_completion_line(tool_name: str, ms: int) -> str:
    label = _TOOL_LABELS.get(tool_name, tool_name.capitalize())
    return f"{label} completed in {format_duration_ms(ms)}."
