from __future__ import annotations

import json
import logging
import time
from collections.abc import Generator
from typing import Any

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from smith.core.config import Config, normalize_deepseek_model
from smith.llm.base import (
    LLMProvider,
    LLMResponse,
    StreamEvent,
    TokenUsage,
    ToolCall,
    ToolDef,
)

logger = logging.getLogger(__name__)

DEEPSEEK_BASE_URL = "https://api.deepseek.com"


def _to_openai_tools(
    tools: list[ToolDef] | None,
) -> list[dict[str, Any]] | None:
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


def _parse_tool_calls(message: Any) -> tuple[ToolCall, ...]:
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


def _parse_usage(response: Any) -> TokenUsage | None:
    if not hasattr(response, "usage") or response.usage is None:
        return None
    return TokenUsage(
        prompt_tokens=response.usage.prompt_tokens or 0,
        completion_tokens=response.usage.completion_tokens or 0,
        total_tokens=response.usage.total_tokens or 0,
    )


class DeepSeekProvider(LLMProvider):
    def __init__(self, config: Config, client: OpenAI | None = None) -> None:
        self._config = config
        self._client = client or OpenAI(
            api_key=config.deepseek_api_key,
            base_url=DEEPSEEK_BASE_URL,
        )

    @property
    def name(self) -> str:
        return "DeepSeek"

    def _build_messages(
        self,
        prompt: str,
        *,
        system: str | None = None,
    ) -> list[ChatCompletionMessageParam]:
        messages: list[ChatCompletionMessageParam] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _model(self) -> str:
        return normalize_deepseek_model(self._config.deepseek_model)

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        messages = self._build_messages(prompt, system=system)
        model = self._model()
        start = time.perf_counter()
        response = self._client.chat.completions.create(model=model, messages=messages)
        elapsed = time.perf_counter() - start
        content = response.choices[0].message.content or ""
        _log_llm_call(self.name, model, prompt, content, elapsed)
        return content

    def generate_with_tools(
        self,
        prompt: str,
        *,
        system: str | None = None,
        tools: list[ToolDef] | None = None,
    ) -> LLMResponse:
        messages = self._build_messages(prompt, system=system)
        model = self._model()
        openai_tools = _to_openai_tools(tools)
        kwargs: dict[str, Any] = {"model": model, "messages": messages}
        if openai_tools:
            kwargs["tools"] = openai_tools

        start = time.perf_counter()
        response = self._client.chat.completions.create(**kwargs)
        elapsed = time.perf_counter() - start
        choice = response.choices[0]
        content = choice.message.content or ""
        tool_calls = _parse_tool_calls(choice.message)
        usage = _parse_usage(response)
        _log_llm_call(self.name, model, prompt, content, elapsed, tool_calls=tool_calls)
        return LLMResponse(content=content, tool_calls=tool_calls, usage=usage)

    def generate_stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        tools: list[ToolDef] | None = None,
    ) -> Generator[StreamEvent, None, LLMResponse]:
        messages = self._build_messages(prompt, system=system)
        model = self._model()
        openai_tools = _to_openai_tools(tools)
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if openai_tools:
            kwargs["tools"] = openai_tools

        start = time.perf_counter()
        stream = self._client.chat.completions.create(**kwargs)

        content_parts: list[str] = []
        tool_calls_acc: dict[int, dict[str, str]] = {}
        final_usage: TokenUsage | None = None

        for chunk in stream:
            if hasattr(chunk, "usage") and chunk.usage:
                final_usage = TokenUsage(
                    prompt_tokens=chunk.usage.prompt_tokens or 0,
                    completion_tokens=chunk.usage.completion_tokens or 0,
                    total_tokens=chunk.usage.total_tokens or 0,
                )

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            if delta.content:
                content_parts.append(delta.content)
                yield StreamEvent(type="token", content=delta.content)

            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {"id": "", "name": "", "arguments": ""}
                    if tc_delta.id:
                        tool_calls_acc[idx]["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tool_calls_acc[idx]["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            tool_calls_acc[idx]["arguments"] += tc_delta.function.arguments

        # Build final tool calls from accumulated deltas
        tool_calls: tuple[ToolCall, ...] = tuple(
            ToolCall(
                id=data["id"] or f"call_{idx}",
                name=data["name"],
                arguments=data["arguments"] or "{}",
            )
            for idx, data in sorted(tool_calls_acc.items())
        )

        content = "".join(content_parts)
        elapsed = time.perf_counter() - start
        _log_llm_call(self.name, model, prompt, content, elapsed, tool_calls=tool_calls)

        for tc in tool_calls:
            yield StreamEvent(type="tool_call", tool_call=tc)

        result = LLMResponse(content=content, tool_calls=tool_calls, usage=final_usage)
        yield StreamEvent(type="done", usage=final_usage)
        return result

    def generate_structured(
        self,
        prompt: str,
        *,
        system: str | None = None,
        response_model: type,
    ) -> Any:
        sys_msg = (
            system or ""
        ) + "\n\nResponda apenas com JSON válido. Sem markdown, sem explicações."
        content = self.generate(prompt, system=sys_msg)
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning("generate_structured: failed to parse JSON, returning raw string")
            return content


def _log_llm_call(
    provider: str,
    model: str,
    prompt: str,
    content: str,
    elapsed: float,
    *,
    tool_calls: tuple[ToolCall, ...] | None = None,
) -> None:
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
