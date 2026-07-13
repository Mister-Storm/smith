"""OpenAI-compatible helper functions shared by DeepSeek and OpenAI providers."""

from __future__ import annotations

import logging
from typing import Any

from smith.llm.base import TokenUsage, ToolCall, ToolDef

logger = logging.getLogger(__name__)


def to_openai_tools(tools: list[ToolDef] | None) -> list[dict[str, Any]] | None:
    """Convert Smith ToolDefs to OpenAI-compatible tool definitions."""
    if not tools:
        return None
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in tools
    ]


def parse_tool_calls(message: Any) -> tuple[ToolCall, ...]:
    """Extract ToolCall tuples from an OpenAI SDK response message."""
    if not hasattr(message, "tool_calls") or not message.tool_calls:
        return ()
    calls: list[ToolCall] = []
    for tc in message.tool_calls:
        calls.append(
            ToolCall(
                id=tc.id,
                name=tc.function.name,
                arguments=tc.function.arguments,
            )
        )
    return tuple(calls)


def parse_usage(response: Any) -> TokenUsage | None:
    """Extract TokenUsage from an OpenAI SDK response."""
    if not hasattr(response, "usage") or response.usage is None:
        return None
    return TokenUsage(
        prompt_tokens=response.usage.prompt_tokens or 0,
        completion_tokens=response.usage.completion_tokens or 0,
        total_tokens=response.usage.total_tokens or 0,
    )


def log_llm_call(
    provider: str,
    model: str,
    prompt: str,
    content: str,
    elapsed: float,
    *,
    tool_calls: tuple[ToolCall, ...] | None = None,
) -> None:
    """Log a standard LLM call summary."""
    extra = ""
    if tool_calls:
        names = ", ".join(tc.name for tc in tool_calls)
        extra = f" tool_calls=[{names}]"
    logger.info(
        "LLM call provider=%s model=%s prompt_len=%d response_len=%d duration_ms=%.0f%s",
        provider,
        model,
        len(prompt),
        len(content),
        elapsed * 1000,
        extra,
    )
