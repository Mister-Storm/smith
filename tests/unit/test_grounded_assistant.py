from smith.cli.thinking_renderer import ThinkingRenderer
from smith.core.config import Config
from smith.memory.service import MemoryService
from smith.services.chat import ChatService
from tests.conftest import FakeLLMProvider
from tests.helpers.buildtwin_fixture import create_buildtwin_fixture


def test_handle_message_blocks_without_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    empty = tmp_path / "empty"
    empty.mkdir()
    llm = FakeLLMProvider(response="hallucinated structure")
    memory = MemoryService(tmp_path / "test.db")
    config = Config.load(load_env=False)
    service = ChatService(llm, memory, config, workspace=empty)
    try:
        from smith.services.grounded_assistant import handle_message

        out = handle_message(
            "analyze unknown-project structure",
            chat_service=service,
            session_id="test",
            renderer=ThinkingRenderer(enabled=False),
        )
        assert "repository not found" in out.lower()
        assert len(llm.calls) == 0
    finally:
        memory.close()


def test_handle_message_calls_llm_when_evidence_present(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    repo = create_buildtwin_fixture(tmp_path)
    llm = FakeLLMProvider(
        response=(
            "## Answer\nBased on evidence.\n\n"
            "Recommendations\n- Introduce architecture boundaries\n"
        )
    )
    memory = MemoryService(tmp_path / "test.db")
    config = Config.load(load_env=False)
    service = ChatService(llm, memory, config, workspace=tmp_path)
    try:
        from smith.services.grounded_assistant import handle_message

        out = handle_message(
            f"analyze {repo.name} and propose improvements",
            chat_service=service,
            session_id="test",
            renderer=ThinkingRenderer(enabled=False),
        )
        assert len(llm.calls) == 1
        assert "Evidence" in out or "confidence" in out.lower()
        assert "Project Overview" in out or "Architecture" in out or "Recommendations" in out
    finally:
        memory.close()
