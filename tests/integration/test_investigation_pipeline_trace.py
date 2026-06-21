"""Integration and unit tests for investigation pipeline tracing."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pytest

from smith.cli.thinking_renderer import ThinkingRenderer
from smith.core.config import Config
from smith.core.exceptions import INVESTIGATION_FAILURE_MESSAGE
from smith.memory.service import MemoryService
from smith.models.assistant import (
    AssistantSession,
    ContextConfidence,
    EvidenceBundle,
    EvidenceItem,
    EvidenceLevel,
    RepositoryKnowledge,
)
from smith.services.analysis_requirements import build_requirements
from smith.services.assistant_session import reset_assistant_session
from smith.services.capability_registry import get_capability
from smith.services.chat import ChatService
from smith.services.context_acquisition import acquire_evidence
from smith.services.context_orchestrator import ContextOrchestrator
from smith.services.grounded_assistant import handle_message
from tests.conftest import FakeLLMProvider
from tests.helpers.buildtwin_fixture import create_buildtwin_fixture

BUILDTWIN = Path("/home/mister-storm/development/BuildTwin")


def test_session_reuse_fallback_when_evidence_paths_mismatch(tmp_path):
    repo = create_buildtwin_fixture(tmp_path)
    cap = get_capability("analyze_project")
    req = build_requirements(cap, "analyze BuildTwin and propose improvements")
    session = AssistantSession()
    key = str(repo.resolve())

    session.repository_knowledge_by_path[key] = RepositoryKnowledge(
        frameworks=["Spring Boot"],
        modules=["app"],
    )
    session.investigation_validated_at[key] = time.time()
    session.last_evidence = EvidenceBundle(
        items=[
            EvidenceItem(
                source="filesystem",
                summary="structure",
                detail="modules",
                path=str(tmp_path / "OtherRepo" / "build.gradle.kts"),
                metadata={"evidence_level": EvidenceLevel.STRUCTURE.value},
            ),
            EvidenceItem(
                source="filesystem",
                summary="config",
                detail="gradle",
                path=str(tmp_path / "OtherRepo" / "settings.gradle.kts"),
                metadata={"evidence_level": EvidenceLevel.CONFIGURATION.value},
            ),
            EvidenceItem(
                source="filesystem",
                summary="source",
                detail="class App",
                path=str(tmp_path / "OtherRepo" / "App.kt"),
                metadata={"evidence_level": EvidenceLevel.SOURCE_CODE.value},
            ),
        ],
        confidence=ContextConfidence(
            repository_identification=0.9,
            framework_detection=0.9,
            architecture_detection=0.9,
            project_understanding=0.9,
        ),
    )

    bundle, knowledge_map, _report = acquire_evidence(
        req,
        capability=cap,
        repo_paths=[repo],
        session=session,
        renderer=ThinkingRenderer(enabled=False),
    )

    assert bundle.items
    assert repo in knowledge_map
    assert any(
        (item.metadata or {}).get("evidence_level") == EvidenceLevel.STRUCTURE.value
        for item in bundle.items
        if item.source == "filesystem"
    )


def test_investigation_failure_on_empty_bundle_with_resolved_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    cwd = tmp_path / "smith"
    cwd.mkdir()
    repo = create_buildtwin_fixture(tmp_path, with_cache=False)

    llm = FakeLLMProvider(response="Should not be called")
    memory = MemoryService(tmp_path / "test.db")
    config = Config.load(load_env=False)
    service = ChatService(llm, memory, config, workspace=cwd)

    class EmptyBundleOrchestrator(ContextOrchestrator):
        def orchestrate(self, capability, **kwargs):
            result = super().orchestrate(capability, **kwargs)
            if result.resolved_paths:
                result.bundle.items = []
            return result

    import smith.services.grounded_assistant as grounded_module

    original = grounded_module.ContextOrchestrator
    grounded_module.ContextOrchestrator = EmptyBundleOrchestrator
    try:
        out = handle_message(
            "Analyze BuildTwin",
            chat_service=service,
            session_id="test",
            renderer=ThinkingRenderer(enabled=False),
        )
        assert INVESTIGATION_FAILURE_MESSAGE in out
        assert len(llm.calls) == 0
    finally:
        grounded_module.ContextOrchestrator = original
        memory.close()


def test_debug_trace_logs_acquisition(caplog, tmp_path):
    caplog.set_level(logging.DEBUG, logger="smith.services")
    repo = create_buildtwin_fixture(tmp_path)
    cap = get_capability("analyze_project")
    req = build_requirements(cap, "analyze BuildTwin")
    session = AssistantSession()

    acquire_evidence(
        req,
        capability=cap,
        repo_paths=[repo],
        session=session,
        renderer=ThinkingRenderer(enabled=False),
    )

    messages = " ".join(record.message for record in caplog.records)
    assert "Starting acquisition" in messages
    assert "Evidence bundle" in messages
    assert "Structure collector" in messages


@pytest.mark.skipif(not BUILDTWIN.is_dir(), reason="Real BuildTwin repo not present")
def test_buildtwin_pipeline_populates_evidence(caplog, tmp_path, monkeypatch):
    caplog.set_level(logging.DEBUG, logger="smith.services")
    reset_assistant_session()
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))

    smith_cwd = BUILDTWIN.parent / "smith"
    if not smith_cwd.is_dir():
        smith_cwd = BUILDTWIN.parent

    llm = FakeLLMProvider(response="Project Overview\nKotlin backend\nRecommendations\n- Add tests\n")
    memory = MemoryService(tmp_path / "test-trace.db")
    config = Config.load(load_env=False)
    service = ChatService(llm, memory, config, workspace=smith_cwd)
    try:
        handle_message(
            "Analyze BuildTwin and suggest improvements",
            chat_service=service,
            session_id="trace-test",
            renderer=ThinkingRenderer(enabled=False),
        )
        messages = " ".join(record.message for record in caplog.records)
        assert "Repository resolved" in messages
        assert "Starting acquisition" in messages
        assert "Evidence bundle" in messages
        assert "Bundle received from acquisition" in messages
        assert "Preparing LLM prompt" in messages
        assert len(llm.calls) == 1
        prompt = llm.calls[0][0]
        assert "Repository investigation findings" in prompt
    finally:
        memory.close()
