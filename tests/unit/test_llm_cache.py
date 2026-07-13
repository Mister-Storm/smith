"""Tests for the LLM response cache."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from smith.llm.base import LLMProvider, LLMResponse, ToolCall, ToolDef
from smith.llm.cache import CachedLLMProvider, LLMCache


class _PassthroughProvider(LLMProvider):
    """Simple provider that returns the prompt mirrored back."""

    def __init__(self) -> None:
        self.call_count = 0

    @property
    def name(self) -> str:
        return "Passthrough"

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        self.call_count += 1
        return f"response:{prompt}"

    def generate_with_tools(
        self,
        prompt: str,
        *,
        system: str | None = None,
        tools: list[ToolDef] | None = None,
    ) -> LLMResponse:
        self.call_count += 1
        if tools:
            return LLMResponse(
                content="",
                tool_calls=(ToolCall(id="c1", name="test_tool", arguments="{}"),),
            )
        return LLMResponse(content=f"response:{prompt}")


class TestLLMCache:
    def test_should_return_none_on_miss(self) -> None:
        cache = LLMCache()
        assert cache.get("hello") is None

    def test_should_store_and_retrieve(self) -> None:
        cache = LLMCache()
        cache.set("hello", "world")
        assert cache.get("hello") == "world"

    def test_should_hit_and_miss_counters(self) -> None:
        cache = LLMCache()
        assert cache.get("x") is None
        assert cache.misses == 1
        assert cache.hits == 0
        cache.set("x", "y")
        assert cache.get("x") == "y"
        assert cache.hits == 1
        assert cache.misses == 1

    def test_should_differentiate_by_system_prompt(self) -> None:
        cache = LLMCache()
        cache.set("hello", "no-system")
        cache.set("hello", "with-system", system="system")
        assert cache.get("hello") == "no-system"
        assert cache.get("hello", system="system") == "with-system"

    def test_should_evict_lru_when_full(self) -> None:
        cache = LLMCache(maxsize=3)
        cache.set("a", "1")
        cache.set("b", "2")
        cache.set("c", "3")
        cache.set("d", "4")  # evicts 'a'
        assert cache.get("a") is None
        assert cache.get("b") == "2"
        assert cache.get("d") == "4"
        assert cache.size == 3

    def test_should_expire_after_ttl(self) -> None:
        cache = LLMCache(ttl_seconds=0.05)
        cache.set("hello", "world")
        assert cache.get("hello") == "world"
        time.sleep(0.06)
        assert cache.get("hello") is None

    def test_should_clear_all_entries(self) -> None:
        cache = LLMCache()
        cache.set("a", "1")
        cache.set("b", "2")
        cache.clear()
        assert cache.size == 0
        assert cache.hits == 0

    def test_should_invalidate_single_entry(self) -> None:
        cache = LLMCache()
        cache.set("a", "1")
        assert cache.invalidate("a") is True
        assert cache.invalidate("nonexistent") is False
        assert cache.get("a") is None

    def test_should_report_stats(self) -> None:
        cache = LLMCache(maxsize=64, ttl_seconds=600)
        cache.set("x", "y")
        cache.get("x")
        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["maxsize"] == 64
        assert stats["ttl_seconds"] == 600
        assert stats["size"] == 1


class TestStubProviderGenerate:
    def test_should_use_provider_on_first_call(self) -> None:
        inner = _PassthroughProvider()
        cached = CachedLLMProvider(inner)
        result = cached.generate("hello")
        assert result == "response:hello"
        assert inner.call_count == 1

    def test_should_return_cached_on_second_call(self) -> None:
        inner = _PassthroughProvider()
        cached = CachedLLMProvider(inner)
        cached.generate("hello")
        cached.generate("hello")
        assert inner.call_count == 1  # only called once

    def test_should_not_cache_different_prompts(self) -> None:
        inner = _PassthroughProvider()
        cached = CachedLLMProvider(inner)
        cached.generate("hello")
        cached.generate("world")
        assert inner.call_count == 2

    def test_should_respect_system_prompt_in_cache_key(self) -> None:
        inner = _PassthroughProvider()
        cached = CachedLLMProvider(inner)
        cached.generate("hello")
        cached.generate("hello", system="sys")
        assert inner.call_count == 2

    def test_should_cache_generate_with_tools_without_tools(self) -> None:
        inner = _PassthroughProvider()
        cached = CachedLLMProvider(inner)
        result = cached.generate_with_tools("hello")
        assert result.content == "response:hello"
        cached.generate_with_tools("hello")
        assert inner.call_count == 1

    def test_should_not_cache_generate_with_tools_with_tools(self) -> None:
        inner = _PassthroughProvider()
        cached = CachedLLMProvider(inner)
        tool = ToolDef(name="x", description="x", parameters={})
        cached.generate_with_tools("hello", tools=[tool])
        cached.generate_with_tools("hello", tools=[tool])
        assert inner.call_count == 2  # not cached

    def test_should_bypass_cache_for_streaming(self) -> None:
        inner = _PassthroughProvider()
        cached = CachedLLMProvider(inner)
        list(cached.generate_stream("hello"))
        list(cached.generate_stream("hello"))
        assert inner.call_count == 2  # streaming always bypasses

    def test_should_cache_structured_on_json_response(self) -> None:
        inner = _PassthroughProvider()
        # Override generate_structured to return parsed JSON
        inner.generate_structured = MagicMock(  # type: ignore
            return_value={"a": 1}
        )
        cached = CachedLLMProvider(inner)
        result = cached.generate_structured("hello", response_model=dict)
        assert result == {"a": 1}
        result2 = cached.generate_structured("hello", response_model=dict)
        assert result2 == {"a": 1}
        assert inner.generate_structured.call_count == 1  # cached

    def test_should_not_cache_structured_on_non_dict_response(self) -> None:
        inner = _PassthroughProvider()
        cached = CachedLLMProvider(inner)
        result = cached.generate_structured("hello", response_model=dict)
        assert result == "response:hello"  # not JSON, returns raw
        cached.generate_structured("hello", response_model=dict)
        assert inner.call_count == 2  # not cached because it's not dict
