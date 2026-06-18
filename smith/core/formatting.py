CONFIG_REQUIRED_MSG = "Configuration required. Run: smith setup"

_TOOL_LABELS = {
    "analyze": "Analysis",
    "context": "Context",
    "summarize": "Summarization",
    "duplicates": "Duplicate scan",
    "organize": "Organization",
}

_NEXT_ACTIONS = {
    "analyze": "smith context .",
    "context": "smith analyze . --structure-only",
    "duplicates": "smith organize ~/Downloads --dry-run",
    "organize": "smith doctor",
    "summarize": "smith chat",
}


def format_duration_ms(ms: int) -> str:
    if ms >= 1000:
        seconds = ms / 1000
        if seconds >= 10:
            return f"{seconds:.0f} seconds"
        return f"{seconds:.1f} seconds"
    return f"{ms} ms"


def format_execution_time(ms: int) -> str:
    if ms >= 1000:
        seconds = ms / 1000
        if seconds >= 10:
            return f"{seconds:.0f}s"
        return f"{seconds:.1f}s"
    return f"{ms}ms"


def format_completion_line(tool_name: str, ms: int) -> str:
    label = _TOOL_LABELS.get(tool_name, tool_name.capitalize())
    return f"{label} completed in {format_duration_ms(ms)}."


def get_next_action(tool_name: str) -> str | None:
    return _NEXT_ACTIONS.get(tool_name)


def format_success_line(tool_name: str) -> str:
    label = _TOOL_LABELS.get(tool_name, tool_name.capitalize())
    return f"✓ {label} completed"


def format_llm_line(provider: str, model: str) -> str:
    return f"Provider: {provider} · Model: {model}"


def format_result_footer(
    tool_name: str,
    ms: int,
    *,
    provider: str | None = None,
    model: str | None = None,
) -> str:
    lines = [
        format_success_line(tool_name),
        f"Execution time: {format_execution_time(ms)}",
    ]
    if provider and model:
        lines.append(format_llm_line(provider, model))
    next_action = get_next_action(tool_name)
    if next_action:
        lines.append(f"Next: {next_action}")
    return "\n".join(lines)
