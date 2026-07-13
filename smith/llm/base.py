from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Generator
from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class ToolDef:
    """Definition of a tool the LLM can call."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema object


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A tool call returned by the LLM."""

    id: str
    name: str
    arguments: str  # JSON string


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Token usage statistics from an LLM response."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Complete response from an LLM."""

    content: str
    tool_calls: tuple[ToolCall, ...] = ()
    usage: TokenUsage | None = None


StreamEventType = Literal["token", "tool_call", "done", "error"]


@dataclass(frozen=True, slots=True)
class StreamEvent:
    """A single event in a streaming LLM response."""

    type: StreamEventType
    content: str = ""
    tool_call: ToolCall | None = None
    usage: TokenUsage | None = None


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, *, system: str | None = None) -> str:
        """Simple text generation (backward compatible)."""
        ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    def generate_with_tools(
        self,
        prompt: str,
        *,
        system: str | None = None,
        tools: list[ToolDef] | None = None,
    ) -> LLMResponse:
        """Generate with optional tool calling support.

        Default implementation delegates to generate() and wraps the result.
        Override in providers that support native tool calling.
        """
        content = self.generate(prompt, system=system)
        return LLMResponse(content=content)

    def generate_stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        tools: list[ToolDef] | None = None,
    ) -> Generator[StreamEvent, None, LLMResponse]:
        """Stream a response token by token, yielding StreamEvents.

        Yields StreamEvent for each token / tool_call, then returns the final LLMResponse.
        Default fallback yields a single 'token' event then a 'done' event.
        Override in providers that support native streaming.
        """
        result = self.generate_with_tools(prompt, system=system, tools=tools)
        if result.content:
            yield StreamEvent(type="token", content=result.content)
        for tc in result.tool_calls:
            yield StreamEvent(type="tool_call", tool_call=tc)
        yield StreamEvent(type="done", usage=result.usage)
        return result

    def generate_structured(
        self,
        prompt: str,
        *,
        system: str | None = None,
        response_model: type,
    ) -> Any:
        """Generate a structured (typed) response.

        Default: generate text and return as-is. Override in providers
        that support native structured output (JSON mode / response_format).
        """
        return self.generate(prompt, system=system)
