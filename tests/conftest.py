import pytest

from smith.core.config import Config
from smith.llm.base import LLMProvider
from smith.memory.service import MemoryService


class FakeLLMProvider(LLMProvider):
    def __init__(self, response: str = "fake response") -> None:
        self._response = response
        self.calls: list[tuple[str, str | None]] = []

    @property
    def name(self) -> str:
        return "Fake"

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self._response


@pytest.fixture
def fake_llm() -> FakeLLMProvider:
    return FakeLLMProvider()


@pytest.fixture
def memory_service(tmp_path) -> MemoryService:
    db_path = tmp_path / "test.db"
    service = MemoryService(db_path)
    yield service
    service.close()


@pytest.fixture
def config_with_openai(monkeypatch) -> Config:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("SMITH_LLM_PROVIDER", raising=False)
    return Config.load()


@pytest.fixture
def config_with_deepseek(monkeypatch) -> Config:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-deepseek")
    monkeypatch.delenv("SMITH_LLM_PROVIDER", raising=False)
    return Config.load()
