import pytest

from smith.core.config import Config
from smith.llm.base import LLMProvider
from smith.memory.service import MemoryService
from tests.helpers.git_repo import init_git_repo


@pytest.fixture
def git_repo(tmp_path):
    return init_git_repo(tmp_path)


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


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch):
    monkeypatch.setenv("SMITH_SKIP_DOTENV", "1")
    monkeypatch.setenv("SMITH_NO_COLOR", "1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("SMITH_LLM_PROVIDER", raising=False)
    from smith.services.planner import set_last_planning_result

    set_last_planning_result(None)
    yield
    set_last_planning_result(None)


@pytest.fixture
def config_with_openai(monkeypatch) -> Config:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("SMITH_LLM_PROVIDER", raising=False)
    return Config.load(load_env=False)


@pytest.fixture
def config_with_deepseek(monkeypatch) -> Config:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-deepseek")
    monkeypatch.delenv("SMITH_LLM_PROVIDER", raising=False)
    return Config.load(load_env=False)
