"""Acceptance tests for cache bypass fix and mandatory investigation."""

from smith.cli.thinking_renderer import ThinkingRenderer
from smith.core.config import Config
from smith.memory.service import MemoryService
from smith.models.assistant import AssistantSession, ContextConfidence, EvidenceBundle
from smith.services.capability_registry import get_capability
from smith.services.chat import ChatService
from smith.services.context_orchestrator import ContextOrchestrator, _resolve_repo_paths
from smith.services.grounded_assistant import handle_message
from smith.services.grounded_response import format_blocked_response
from tests.conftest import FakeLLMProvider
from tests.helpers.buildtwin_fixture import create_buildtwin_fixture


def test_buildtwin_sibling_with_cache_investigates(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    cwd = tmp_path / "smith"
    cwd.mkdir()
    create_buildtwin_fixture(tmp_path, with_cache=True)

    llm = FakeLLMProvider(response="Recommendations\n- Improve test coverage\n")
    memory = MemoryService(tmp_path / "test.db")
    config = Config.load(load_env=False)
    service = ChatService(llm, memory, config, workspace=cwd)
    try:
        out = handle_message(
            "Analyze BuildTwin and propose improvements",
            chat_service=service,
            session_id="test",
            renderer=ThinkingRenderer(enabled=False),
        )
        assert len(llm.calls) == 1
        assert "Optional context" not in out
        assert "Cached hint" not in out or "filesystem" in out.lower()
        assert "Project Overview" in out or "Recommendations" in out or "Architecture" in out
    finally:
        memory.close()


def test_orchestrator_no_fallthrough_when_unresolved(tmp_path):
    cap = get_capability("analyze_project")
    session = AssistantSession()
    orchestrator = ContextOrchestrator(cwd=tmp_path / "missing")
    result = orchestrator.orchestrate(
        cap,
        message="analyze something",
        session=session,
        resolved_paths={},
    )
    assert "Repository path not resolved" in " ".join(result.missing)
    assert not any("Optional context" in item.summary for item in result.bundle.items)


def test_orchestrator_investigates_not_cache_only(tmp_path):
    repo = create_buildtwin_fixture(tmp_path, with_cache=True)
    cap = get_capability("analyze_project")
    session = AssistantSession()
    orchestrator = ContextOrchestrator(cwd=repo)
    result = orchestrator.orchestrate(
        cap,
        message="analyze BuildTwin",
        session=session,
        resolved_paths={"BuildTwin": repo},
        renderer=ThinkingRenderer(enabled=False),
    )
    levels = {
        (item.metadata or {}).get("evidence_level")
        for item in result.bundle.items
        if item.source == "filesystem"
    }
    assert "structure" in levels
    assert "configuration" in levels
    assert result.knowledge_by_path


def test_blocked_response_no_user_file_requests():
    text = format_blocked_response(["Missing filesystem evidence: configuration"], 0.2)
    assert "provide source" not in text.lower()
    assert "provide files" not in text.lower()
    assert "I could not inspect the repository contents." in text
    assert "Investigation attempted" in text
    assert "RepositoryKnowledge" not in text
    assert "smith context" not in text.lower()


def test_review_code_is_investigative():
    from smith.services.analysis_requirements import is_investigative_capability

    assert is_investigative_capability("review_code")


def test_resolve_repo_paths_prefers_resolved():
    from pathlib import Path

    primary = Path("/tmp/primary")
    paths = {"BuildTwin": Path("/tmp/buildtwin")}
    assert _resolve_repo_paths(paths, primary, Path("/tmp/cwd")) == [Path("/tmp/buildtwin")]


def test_resolve_repo_paths_skips_cwd_when_name_refs_unresolved():
    from pathlib import Path

    assert _resolve_repo_paths({}, None, Path("/tmp/cwd"), name_refs=["BuildTwing"]) == []


def test_resolve_repo_paths_skips_cwd_when_lowercase_name_unresolved():
    from pathlib import Path

    assert _resolve_repo_paths({}, None, Path("/tmp/cwd"), name_refs=["my-api"]) == []


def test_lowercase_not_found_shows_nearby(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    cwd = tmp_path / "smith"
    cwd.mkdir()
    create_buildtwin_fixture(tmp_path, with_cache=False)

    llm = FakeLLMProvider(response="Should not be called")
    memory = MemoryService(tmp_path / "test.db")
    config = Config.load(load_env=False)
    service = ChatService(llm, memory, config, workspace=cwd)
    try:
        out = handle_message(
            "Analyze my-api architecture",
            chat_service=service,
            session_id="test",
            renderer=ThinkingRenderer(enabled=False),
        )
        assert len(llm.calls) == 0
        assert "Repository not found" in out
        assert "Projects found nearby" in out
        assert "BuildTwin" in out
    finally:
        memory.close()


def test_lowercase_sibling_investigates(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    cwd = tmp_path / "smith"
    sibling = tmp_path / "my-api"
    cwd.mkdir()
    sibling.mkdir()
    (sibling / "pyproject.toml").write_text("[tool.poetry]\nname='my-api'\n", encoding="utf-8")
    (sibling / "README.md").write_text("# my-api\n", encoding="utf-8")
    src = sibling / "src" / "my_api"
    src.mkdir(parents=True)
    (src / "main.py").write_text("def run():\n    return 'ok'\n", encoding="utf-8")
    (src / "service.py").write_text("class ApiService:\n    pass\n", encoding="utf-8")

    llm = FakeLLMProvider(response="Project Overview\nAPI service\nRecommendations\n- Add tests\n")
    memory = MemoryService(tmp_path / "test.db")
    config = Config.load(load_env=False)
    service = ChatService(llm, memory, config, workspace=cwd)
    try:
        out = handle_message(
            "Analyze my-api and propose improvements",
            chat_service=service,
            session_id="test",
            renderer=ThinkingRenderer(enabled=False),
        )
        assert len(llm.calls) == 1
        assert "Repository not found" not in out
        assert "Recommendations" in out or "Project Overview" in out
    finally:
        memory.close()


def test_llm_called_without_substantive_knowledge():
    from smith.models.assistant import EvidenceItem, EvidenceLevel
    from smith.services.grounded_response import should_generate_llm_response

    cap = get_capability("analyze_project")
    bundle = EvidenceBundle(
        items=[
            EvidenceItem(
                source="filesystem",
                summary="structure",
                detail="modules",
                metadata={"evidence_level": EvidenceLevel.STRUCTURE.value},
            ),
            EvidenceItem(
                source="filesystem",
                summary="config",
                detail="gradle",
                metadata={"evidence_level": EvidenceLevel.CONFIGURATION.value},
            ),
        ],
        confidence=ContextConfidence(
            repository_identification=0.8,
            framework_detection=0.8,
            architecture_detection=0.8,
            project_understanding=0.8,
        ),
    )
    allowed, reasons = should_generate_llm_response(
        cap,
        bundle,
        knowledge=None,
        message="analyze BuildTwin",
    )
    assert allowed, reasons


def test_typo_suggests_buildtwin(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    cwd = tmp_path / "smith"
    cwd.mkdir()
    create_buildtwin_fixture(tmp_path, with_cache=False)

    from smith.services.repository_resolution import resolve_repository_reference

    result = resolve_repository_reference("BuildTwing", cwd=cwd)
    assert result.status.value == "not_found"
    assert "BuildTwin" in result.suggestions


def test_typo_handle_message_no_llm(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    cwd = tmp_path / "smith"
    cwd.mkdir()
    create_buildtwin_fixture(tmp_path, with_cache=False)

    llm = FakeLLMProvider(response="Should not be called")
    memory = MemoryService(tmp_path / "test.db")
    config = Config.load(load_env=False)
    service = ChatService(llm, memory, config, workspace=cwd)
    try:
        out = handle_message(
            "Analyze BuildTwing",
            chat_service=service,
            session_id="test",
            renderer=ThinkingRenderer(enabled=False),
        )
        assert len(llm.calls) == 0
        assert "Did you mean BuildTwin?" in out
        assert "RepositoryKnowledge" not in out
    finally:
        memory.close()


def test_no_cwd_fallback_on_failed_name(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    cwd = tmp_path / "smith"
    cwd.mkdir()
    (cwd / "pyproject.toml").write_text("[tool.poetry]\n", encoding="utf-8")
    create_buildtwin_fixture(tmp_path, with_cache=False)

    cap = get_capability("analyze_project")
    session = AssistantSession()
    orchestrator = ContextOrchestrator(cwd=cwd)
    result = orchestrator.orchestrate(
        cap,
        message="Analyze BuildTwing",
        session=session,
        resolved_paths={},
        name_refs=["BuildTwing"],
        renderer=ThinkingRenderer(enabled=False),
    )
    assert result.bundle.items == [] or not any(
        item.path == str(cwd.resolve()) for item in result.bundle.items if item.path
    )


def test_portuguese_frontend_after_buildtwin_session(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    cwd = tmp_path / "smith"
    frontend = tmp_path / "buildtwin-frontend"
    cwd.mkdir()
    create_buildtwin_fixture(tmp_path, with_cache=False)
    frontend.mkdir()
    (frontend / "package.json").write_text('{"name":"buildtwin-frontend"}\n', encoding="utf-8")
    (frontend / "README.md").write_text("# buildtwin-frontend\n", encoding="utf-8")
    src = frontend / "src" / "app"
    src.mkdir(parents=True)
    (src / "page.tsx").write_text("export default function Page() { return null }\n", encoding="utf-8")
    (src / "layout.tsx").write_text("export default function Layout({ children }) { return children }\n", encoding="utf-8")

    llm = FakeLLMProvider(response="Project Overview\nNext.js frontend\nRecommendations\n- Add tests\n")
    memory = MemoryService(tmp_path / "test.db")
    config = Config.load(load_env=False)
    service = ChatService(llm, memory, config, workspace=cwd)
    try:
        handle_message(
            "Analyze BuildTwin and suggest improvements",
            chat_service=service,
            session_id="test",
            renderer=ThinkingRenderer(enabled=False),
        )
        llm.calls.clear()
        out = handle_message(
            "analise o projeto buildTwin-frontend e proponha melhorias",
            chat_service=service,
            session_id="test",
            renderer=ThinkingRenderer(enabled=False),
        )
        assert "Repository investigation failed unexpectedly" not in out
        assert len(llm.calls) == 1
        assert "Recommendations" in out or "Project Overview" in out
    finally:
        memory.close()


def test_buildtwin_one_directory_above(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    cwd = tmp_path / "smith"
    cwd.mkdir()
    create_buildtwin_fixture(tmp_path, with_cache=True)

    llm = FakeLLMProvider(response="Project Overview\nKotlin backend\nRecommendations\n- Add tests\n")
    memory = MemoryService(tmp_path / "test.db")
    config = Config.load(load_env=False)
    service = ChatService(llm, memory, config, workspace=cwd)
    try:
        out = handle_message(
            "Analyze BuildTwin one directory above and suggest improvements",
            chat_service=service,
            session_id="test",
            renderer=ThinkingRenderer(enabled=False),
        )
        assert len(llm.calls) == 1
        prompt = llm.calls[0][0]
        assert "RepositoryKnowledge" not in prompt
        assert "Repository investigation findings" in prompt
        assert "RepositoryKnowledge" not in out
        assert "Recommendations" in out or "Project Overview" in out
    finally:
        memory.close()
