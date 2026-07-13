from __future__ import annotations

import json
import logging
import time
from collections.abc import Generator
from typing import Any

from openai import OpenAI

from smith.core.config import Config
from smith.llm._openai_compat import (
    log_llm_call,
    parse_tool_calls,
    parse_usage,
    to_openai_tools,
)
from smith.llm.base import LLMProvider, LLMResponse, StreamEvent, TokenUsage, ToolCall, ToolDef

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    def __init__(self, config: Config, client: OpenAI | None = None) -> None:
        self._config = config
        self._client = client or OpenAI(api_key=config.openai_api_key)

    @property
    def name(self) -> str:
        return "OpenAI"

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        start = time.perf_counter()
        response = self._client.chat.completions.create(
            model=self._config.openai_model,
            messages=messages,
        )
        elapsed = time.perf_counter() - start
        content = response.choices[0].message.content or ""
        log_llm_call(self.name, self._config.openai_model, prompt, content, elapsed)
        return content

    def generate_with_tools(
        self,
        prompt: str,
        *,
        system: str | None = None,
        tools: list[ToolDef] | None = None,
    ) -> LLMResponse:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        openai_tools = to_openai_tools(tools)
        kwargs: dict[str, Any] = {
            "model": self._config.openai_model,
            "messages": messages,
        }
        if openai_tools:
            kwargs["tools"] = openai_tools

        start = time.perf_counter()
        response = self._client.chat.completions.create(**kwargs)
        elapsed = time.perf_counter() - start
        choice = response.choices[0]
        content = choice.message.content or ""
        tool_calls = parse_tool_calls(choice.message)
        usage = parse_usage(response)
        log_llm_call(
            self.name,
            self._config.openai_model,
            prompt,
            content,
            elapsed,
            tool_calls=tool_calls,
        )
        return LLMResponse(content=content, tool_calls=tool_calls, usage=usage)

    def generate_stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        tools: list[ToolDef] | None = None,
    ) -> Generator[StreamEvent, None, LLMResponse]:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        openai_tools = to_openai_tools(tools)
        kwargs: dict[str, Any] = {
            "model": self._config.openai_model,
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
        log_llm_call(
            self.name,
            self._config.openai_model,
            prompt,
            content,
            elapsed,
            tool_calls=tool_calls,
        )

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
        messages: list[dict[str, str]] = [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": prompt},
        ]

        start = time.perf_counter()
        response = self._client.chat.completions.create(
            model=self._config.openai_model,
            messages=messages,
            response_format={"type": "json_object"},
        )
        elapsed = time.perf_counter() - start
        content = response.choices[0].message.content or ""
        log_llm_call(self.name, self._config.openai_model, prompt, content, elapsed)

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning("generate_structured: failed to parse JSON, returning raw string")
            return content
