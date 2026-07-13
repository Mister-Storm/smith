"""LRU cache with TTL for LLM responses.

Reduces token usage and latency by reusing responses for identical prompts
within a configurable time window.
"""

from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from collections.abc import Generator

from smith.llm.base import (
    LLMProvider,
    LLMResponse,
    StreamEvent,
    ToolDef,
)


class LLMCache:
    """A simple LRU cache with TTL for LLM responses.

    Cache keys are MD5 hashes of (system + prompt). Stale entries
    are evicted on access. When full, the least recently used entry
    is evicted.
    """

    def __init__(self, maxsize: int = 128, ttl_seconds: float = 300) -> None:
        self._cache: OrderedDict[str, tuple[float, str]] = OrderedDict()
        self._maxsize = maxsize
        self._ttl = ttl_seconds
        self._hits = 0
        self._misses = 0

    @property
    def hits(self) -> int:
        return self._hits

    @property
    def misses(self) -> int:
        return self._misses

    @property
    def size(self) -> int:
        return len(self._cache)

    def _make_key(self, prompt: str, system: str | None = None) -> str:
        raw = f"{system or ''}|{prompt}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, prompt: str, system: str | None = None) -> str | None:
        """Return cached response or None if missing or stale."""
        key = self._make_key(prompt, system)
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None
        expires_at, response = entry
        if time.monotonic() > expires_at:
            del self._cache[key]
            self._misses += 1
            return None
        self._cache.move_to_end(key)
        self._hits += 1
        return response

    def set(self, prompt: str, response: str, system: str | None = None) -> None:
        """Store a response in the cache."""
        key = self._make_key(prompt, system)
        expires_at = time.monotonic() + self._ttl
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = (expires_at, response)
        while len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def invalidate(self, prompt: str, system: str | None = None) -> bool:
        """Remove a single entry. Returns True if it existed."""
        key = self._make_key(prompt, system)
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def stats(self) -> dict[str, int | float]:
        """Return cache statistics."""
        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": len(self._cache),
            "maxsize": self._maxsize,
            "ttl_seconds": self._ttl,
        }


class CachedLLMProvider(LLMProvider):
    """Wraps an LLMProvider with a response cache.

    Caches only plain text responses (no tool calls). Streaming and
    tool-calling requests bypass the cache.
    """

    def __init__(
        self,
        provider: LLMProvider,
        cache: LLMCache | None = None,
    ) -> None:
        self._provider = provider
        self._cache = cache or LLMCache()

    @property
    def name(self) -> str:
        return self._provider.name

    @property
    def cache(self) -> LLMCache:
        return self._cache

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        cached = self._cache.get(prompt, system)
        if cached is not None:
            return cached
        response = self._provider.generate(prompt, system=system)
        self._cache.set(prompt, response, system)
        return response

    def generate_with_tools(
        self,
        prompt: str,
        *,
        system: str | None = None,
        tools: list[ToolDef] | None = None,
    ) -> LLMResponse:
        if not tools:
            cached = self._cache.get(prompt, system)
            if cached is not None:
                return LLMResponse(content=cached)
        response = self._provider.generate_with_tools(prompt, system=system, tools=tools)
        if not tools and not response.tool_calls:
            self._cache.set(prompt, response.content, system)
        return response

    def generate_stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        tools: list[ToolDef] | None = None,
    ) -> Generator[StreamEvent, None, LLMResponse]:
        # Streaming always bypasses cache to maintain real-time UX
        yield from self._provider.generate_stream(prompt, system=system, tools=tools)

    def generate_structured(
        self,
        prompt: str,
        *,
        system: str | None = None,
        response_model: type,
    ) -> object:
        cached = self._cache.get(prompt, system)
        if cached is not None:
            import json

            try:
                return json.loads(cached)
            except json.JSONDecodeError:
                pass
        response = self._provider.generate_structured(
            prompt, system=system, response_model=response_model
        )
        if isinstance(response, (dict, list)):
            import json

            self._cache.set(prompt, json.dumps(response), system)
        return response
