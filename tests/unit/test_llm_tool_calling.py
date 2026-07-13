from __future__ import annotations

from unittest.mock import MagicMock

from smith.llm.base import (
    LLMProvider,
    LLMResponse,
    StreamEvent,
    TokenUsage,
    ToolCall,
    ToolDef,
)

# ── Dataclass tests ──────────────────────────────────────────────


class TestToolDef:
    def test_should_create_tool_def_with_schema(self) -> None:
        td = ToolDef(
            name="get_weather",
            description="Get weather for a city",
            parameters={
                "type": "object",
                "properties": {"city": {"type": "string"}},
            },
        )
        assert td.name == "get_weather"
        assert td.description == "Get weather for a city"
        assert "city" in td.parameters["properties"]


class TestToolCall:
    def test_should_create_tool_call(self) -> None:
        tc = ToolCall(id="call_1", name="get_weather", arguments='{"city": "Luanda"}')
        assert tc.id == "call_1"
        assert tc.name == "get_weather"
        assert tc.arguments == '{"city": "Luanda"}'


class TestTokenUsage:
    def test_should_create_token_usage(self) -> None:
        tu = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        assert tu.prompt_tokens == 100
        assert tu.completion_tokens == 50
        assert tu.total_tokens == 150


class TestLLMResponse:
    def test_should_create_text_response(self) -> None:
        resp = LLMResponse(content="Hello")
        assert resp.content == "Hello"
        assert resp.tool_calls == ()
        assert resp.usage is None

    def test_should_create_response_with_tool_calls(self) -> None:
        tc = ToolCall(id="c1", name="search", arguments='{"q": "test"}')
        tu = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        resp = LLMResponse(content="", tool_calls=(tc,), usage=tu)
        assert resp.tool_calls == (tc,)
        assert resp.usage == tu


class TestStreamEvent:
    def test_should_create_token_event(self) -> None:
        ev = StreamEvent(type="token", content="Hello")
        assert ev.type == "token"
        assert ev.content == "Hello"

    def test_should_create_tool_call_event(self) -> None:
        tc = ToolCall(id="c1", name="search", arguments="{}")
        ev = StreamEvent(type="tool_call", tool_call=tc)
        assert ev.type == "tool_call"
        assert ev.tool_call == tc

    def test_should_create_done_event(self) -> None:
        tu = TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2)
        ev = StreamEvent(type="done", usage=tu)
        assert ev.type == "done"
        assert ev.usage == tu


# ── Stub provider ────────────────────────────────────────────────


class _StubProvider(LLMProvider):
    @property
    def name(self) -> str:
        return "Stub"

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        return f"response to: {prompt}"


class TestDefaultImplementations:
    def test_should_default_generate_with_tools_to_text(self) -> None:
        provider = _StubProvider()
        result = provider.generate_with_tools("hello")
        assert isinstance(result, LLMResponse)
        assert result.content == "response to: hello"
        assert result.tool_calls == ()

    def test_should_default_generate_stream_to_single_event(self) -> None:
        provider = _StubProvider()
        gen = provider.generate_stream("hello")
        events = list(gen)
        assert len(events) >= 2
        assert events[0].type == "token"
        assert events[-1].type == "done"

    def test_should_default_generate_structured_to_text(self) -> None:
        provider = _StubProvider()
        result = provider.generate_structured("hello", response_model=str)
        assert result == "response to: hello"


# ── Mocks ────────────────────────────────────────────────────────


def _mock_chunk(content: str | None = None) -> MagicMock:
    chunk = MagicMock()
    delta = MagicMock()
    delta.content = content
    delta.tool_calls = None
    choice = MagicMock()
    choice.delta = delta
    chunk.choices = [choice]
    chunk.usage = None
    return chunk


def _mock_tool_call_chunk(
    delta_index: int = 0,
    tc_id: str | None = None,
    tc_name: str | None = None,
    tc_args: str | None = None,
) -> MagicMock:
    chunk = MagicMock()
    delta = MagicMock()
    delta.content = None
    tc_mock = MagicMock()
    tc_mock.index = delta_index
    tc_mock.id = tc_id
    func = MagicMock()
    func.name = tc_name
    func.arguments = tc_args
    tc_mock.function = func
    delta.tool_calls = [tc_mock]
    choice = MagicMock()
    choice.delta = delta
    chunk.choices = [choice]
    chunk.usage = None
    return chunk


def _mock_response(content: str, tool_calls: list | None = None) -> MagicMock:
    resp = MagicMock()
    choice = MagicMock()
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls
    choice.message = msg
    resp.choices = [choice]
    resp.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    return resp


# ── DeepSeek tests ───────────────────────────────────────────────


class TestDeepSeekProviderToolCalling:
    def test_should_return_tool_calls_in_response(self) -> None:
        from smith.core.config import Config
        from smith.llm.deepseek_provider import DeepSeekProvider

        config = Config()
        mock_client = MagicMock()
        tc = MagicMock()
        tc.id = "call_abc"
        tc.function.name = "analyze_project"
        tc.function.arguments = '{"path": "."}'
        mock_client.chat.completions.create.return_value = _mock_response(
            content="",
            tool_calls=[tc],
        )

        provider = DeepSeekProvider(config, client=mock_client)
        tools = [
            ToolDef(
                name="analyze_project",
                description="Analyze a project",
                parameters={
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                },
            )
        ]
        result = provider.generate_with_tools("analyze this", tools=tools)

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "analyze_project"
        assert result.tool_calls[0].arguments == '{"path": "."}'
        assert result.usage is not None
        assert result.usage.total_tokens == 15

    def test_should_generate_text_without_tools(self) -> None:
        from smith.core.config import Config
        from smith.llm.deepseek_provider import DeepSeekProvider

        config = Config()
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_response(content="Hello world")

        provider = DeepSeekProvider(config, client=mock_client)
        result = provider.generate_with_tools("say hi")
        assert result.content == "Hello world"
        assert result.tool_calls == ()

    def test_should_stream_tokens(self) -> None:
        from smith.core.config import Config
        from smith.llm.deepseek_provider import DeepSeekProvider

        config = Config()
        mock_client = MagicMock()

        chunks = [
            _mock_chunk("Hello"),
            _mock_chunk(" world"),
            _mock_chunk("!"),
        ]
        final = _mock_chunk(None)
        final.usage = MagicMock(prompt_tokens=5, completion_tokens=3, total_tokens=8)
        mock_client.chat.completions.create.return_value = chunks + [final]

        provider = DeepSeekProvider(config, client=mock_client)
        events = list(provider.generate_stream("say hi"))
        tokens = [e.content for e in events if e.type == "token"]
        done = [e for e in events if e.type == "done"]

        assert "".join(tokens) == "Hello world!"
        assert len(done) == 1
        assert done[0].usage is not None
        assert done[0].usage.total_tokens == 8

    def test_should_stream_tool_calls(self) -> None:
        from smith.core.config import Config
        from smith.llm.deepseek_provider import DeepSeekProvider

        config = Config()
        mock_client = MagicMock()

        tool_def = ToolDef(
            name="search_docs",
            description="Search documentation",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
            },
        )

        # Two streaming chunks: name arrives first, then args
        chunks = [
            _mock_chunk("I will search..."),
            _mock_tool_call_chunk(
                delta_index=0, tc_id="call_1", tc_name="search_docs", tc_args='{"query": "'
            ),
            _mock_tool_call_chunk(delta_index=0, tc_id=None, tc_name=None, tc_args='pytest"}'),
        ]
        final = _mock_chunk(None)
        final.usage = MagicMock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        mock_client.chat.completions.create.return_value = chunks + [final]

        provider = DeepSeekProvider(config, client=mock_client)
        events = list(provider.generate_stream("search pytest", tools=[tool_def]))

        tool_call_events = [e for e in events if e.type == "tool_call"]
        done_events = [e for e in events if e.type == "done"]

        assert len(tool_call_events) == 1
        assert tool_call_events[0].tool_call is not None
        assert tool_call_events[0].tool_call.name == "search_docs"
        assert '{"query": "pytest"}' in tool_call_events[0].tool_call.arguments
        assert len(done_events) == 1


# ── OpenAI tests ─────────────────────────────────────────────────


class TestOpenAIProviderToolCalling:
    def test_should_return_structured_json(self) -> None:
        from smith.core.config import Config
        from smith.llm.openai_provider import OpenAIProvider

        config = Config()
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_response(
            content='{"name": "Smith", "version": "0.1.0"}',
        )

        provider = OpenAIProvider(config, client=mock_client)
        result = provider.generate_structured("describe the project", response_model=dict)

        assert isinstance(result, dict)
        assert result["name"] == "Smith"
        assert result["version"] == "0.1.0"

    def test_should_return_tool_calls(self) -> None:
        from smith.core.config import Config
        from smith.llm.openai_provider import OpenAIProvider

        config = Config()
        mock_client = MagicMock()
        tc = MagicMock()
        tc.id = "call_xyz"
        tc.function.name = "run_tests"
        tc.function.arguments = '{"module": "llm"}'
        mock_client.chat.completions.create.return_value = _mock_response(
            content="", tool_calls=[tc]
        )

        provider = OpenAIProvider(config, client=mock_client)
        result = provider.generate_with_tools("run tests")

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "run_tests"
        assert result.tool_calls[0].arguments == '{"module": "llm"}'

    def test_should_stream_tokens(self) -> None:
        from smith.core.config import Config
        from smith.llm.openai_provider import OpenAIProvider

        config = Config()
        mock_client = MagicMock()

        chunks = [
            _mock_chunk("Stream"),
            _mock_chunk("ing"),
            _mock_chunk(" works"),
        ]
        final = _mock_chunk(None)
        final.usage = MagicMock(prompt_tokens=3, completion_tokens=3, total_tokens=6)
        mock_client.chat.completions.create.return_value = chunks + [final]

        provider = OpenAIProvider(config, client=mock_client)
        events = list(provider.generate_stream("test streaming"))
        tokens = [e.content for e in events if e.type == "token"]
        done = [e for e in events if e.type == "done"]

        assert "".join(tokens) == "Streaming works"
        assert len(done) == 1

    def test_should_stream_tool_calls(self) -> None:
        from smith.core.config import Config
        from smith.llm.openai_provider import OpenAIProvider

        config = Config()
        mock_client = MagicMock()

        tool_def = ToolDef(
            name="search_docs",
            description="Search documentation",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
            },
        )

        chunks = [
            _mock_chunk("Thinking..."),
            _mock_tool_call_chunk(
                delta_index=0, tc_id="call_1", tc_name="search_docs", tc_args='{"query": "'
            ),
            _mock_tool_call_chunk(delta_index=0, tc_id=None, tc_name=None, tc_args='pytest"}'),
        ]
        final = _mock_chunk(None)
        final.usage = MagicMock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        mock_client.chat.completions.create.return_value = chunks + [final]

        provider = OpenAIProvider(config, client=mock_client)
        events = list(provider.generate_stream("search pytest", tools=[tool_def]))

        tool_call_events = [e for e in events if e.type == "tool_call"]
        done_events = [e for e in events if e.type == "done"]

        assert len(tool_call_events) == 1
        assert tool_call_events[0].tool_call is not None
        assert tool_call_events[0].tool_call.name == "search_docs"
        assert '{"query": "pytest"}' in tool_call_events[0].tool_call.arguments
        assert len(done_events) == 1


class TestDeepSeekStructured:
    def test_should_return_structured_json(self) -> None:
        from smith.core.config import Config
        from smith.llm.deepseek_provider import DeepSeekProvider

        config = Config()
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_response(
            content='{"name": "Smith", "version": "0.1.0"}',
        )

        provider = DeepSeekProvider(config, client=mock_client)
        result = provider.generate_structured("describe the project", response_model=dict)

        assert isinstance(result, dict)
        assert result["name"] == "Smith"
        assert result["version"] == "0.1.0"

    def test_should_fallback_to_raw_string_on_invalid_json(self) -> None:
        from smith.core.config import Config
        from smith.llm.deepseek_provider import DeepSeekProvider

        config = Config()
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_response(
            content="not valid json",
        )

        provider = DeepSeekProvider(config, client=mock_client)
        result = provider.generate_structured("say hi", response_model=dict)

        assert isinstance(result, str)
        assert result == "not valid json"
