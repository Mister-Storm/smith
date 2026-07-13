"""Tests for grounded_assistant coverage gaps."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from smith.core.exceptions import InvestigationFailure
from smith.models.assistant import (
    AssistantSession,
    RepositoryKnowledge,
    ResolveResult,
    ResolveStatus,
)


@pytest.fixture
def mock_chat_service():
    svc = MagicMock()
    svc._workspace = Path("/home/test")
    svc._config.ui = {}
    svc._config.llm_provider = "openai"
    svc._config.openai_model = "gpt-4o-mini"
    svc._provider = "OpenAI"
    svc._model = "gpt-4o-mini"
    svc._llm = MagicMock()
    svc._memory.get_recent_messages.return_value = []
    return svc


class TestPrimaryKnowledge:
    def test_should_return_none_when_empty(self) -> None:
        from smith.services.grounded_assistant import _primary_knowledge

        assert _primary_knowledge({}) is None

    def test_should_return_first_knowledge(self) -> None:
        from smith.services.grounded_assistant import _primary_knowledge

        k1 = RepositoryKnowledge(
            technologies=["Python"],
            architectural_patterns=["mvc"],
            strengths=[],
            risks=[],
        )
        k2 = RepositoryKnowledge(
            technologies=["Java"],
            architectural_patterns=[],
            strengths=[],
            risks=[],
        )
        result = _primary_knowledge({"/a": k1, "/b": k2})
        assert result is k1


class TestResolveFollowUpKnowledge:
    def test_should_return_fresh_knowledge_for_analysis_target(self) -> None:
        from smith.services.grounded_assistant import _resolve_follow_up_knowledge

        session = AssistantSession()
        session.analysis_target = Path("/target")
        k = RepositoryKnowledge(
            technologies=["Python"],
            architectural_patterns=[],
            strengths=[],
            risks=[],
        )

        with patch("smith.services.grounded_assistant.get_fresh_knowledge", return_value=k):
            result = _resolve_follow_up_knowledge(session)
            assert result is k

    def test_should_return_none_when_no_session_knowledge(self) -> None:
        from smith.services.grounded_assistant import _resolve_follow_up_knowledge

        session = AssistantSession()
        result = _resolve_follow_up_knowledge(session)
        assert result is None


class TestHandleMessageFollowUp:
    def test_should_use_follow_up_knowledge_when_available(self, mock_chat_service) -> None:
        from smith.models.assistant import RepositoryKnowledge
        from smith.services.grounded_assistant import handle_message

        k = RepositoryKnowledge(
            technologies=["Python"],
            architectural_patterns=[],
            strengths=[],
            risks=[],
        )

        with (
            patch("smith.services.grounded_assistant.match_capability") as mock_match,
            patch("smith.services.grounded_assistant.is_knowledge_follow_up", return_value=True),
            patch("smith.services.grounded_assistant._resolve_follow_up_knowledge", return_value=k),
            patch(
                "smith.services.grounded_assistant.answer_from_knowledge",
                return_value="mock answer",
            ),
            patch(
                "smith.services.grounded_assistant.format_grounded_response",
                return_value="Formatted response",
            ),
            patch("smith.services.grounded_assistant.format_result_footer") as mock_footer,
        ):
            mock_match.return_value.id = "general_chat"
            mock_footer.return_value = "\n\n---\nfooter"
            result = handle_message(
                "tell me about the stack",
                chat_service=mock_chat_service,
                session_id="sess-1",
            )
            assert "Formatted response" in result

    def test_should_handle_investigation_failure(self, mock_chat_service) -> None:
        from smith.services.grounded_assistant import handle_message

        with (
            patch("smith.services.grounded_assistant.match_capability") as mock_match,
            patch("smith.services.grounded_assistant.is_knowledge_follow_up", return_value=False),
            patch("smith.services.grounded_assistant.ContextOrchestrator") as mock_orch_cls,
            patch("smith.services.grounded_assistant.format_result_footer") as mock_footer,
        ):
            mock_match.return_value.id = "analyze_project"
            mock_orch = MagicMock()
            mock_orch.orchestrate.side_effect = InvestigationFailure(
                "Investigation failed (resolved=[], items=0)"
            )
            mock_orch_cls.return_value = mock_orch
            mock_footer.return_value = "\n\n---\nfooter"

            result = handle_message(
                "analyze this",
                chat_service=mock_chat_service,
                session_id="sess-1",
            )
            assert "investigação" in result.lower() or "investigation" in result.lower()

    def test_should_return_not_found_when_no_resolved_paths(self, mock_chat_service) -> None:
        from smith.services.grounded_assistant import handle_message

        with (
            patch("smith.services.grounded_assistant.match_capability") as mock_match,
            patch("smith.services.grounded_assistant.is_knowledge_follow_up", return_value=False),
            patch("smith.services.grounded_assistant.extract_references", return_value=["unknown"]),
            patch(
                "smith.services.grounded_assistant.is_likely_repository_name_ref",
                return_value=True,
            ),
            patch(
                "smith.services.grounded_assistant.resolve_references",
                return_value={
                    "unknown": ResolveResult(
                        status=ResolveStatus.NOT_FOUND,
                        suggestions=["proj-a"],
                    )
                },
            ),
            patch("smith.services.grounded_assistant.discover_nearby_projects", return_value=[]),
            patch(
                "smith.services.grounded_assistant.format_not_found_response",
                return_value="Projeto 'unknown' não encontrado",
            ),
            patch("smith.services.grounded_assistant.format_result_footer") as mock_footer,
            patch("smith.services.grounded_assistant.WorkspaceIntelligenceService") as mock_ws,
        ):
            mock_match.return_value.id = "general_chat"
            mock_footer.return_value = "\n\n---\nfooter"
            mock_ws_instance = MagicMock()
            mock_ws_instance.discover_projects.return_value = []
            mock_ws.return_value = mock_ws_instance

            result = handle_message(
                "analyze unknown",
                chat_service=mock_chat_service,
                session_id="sess-1",
            )
            assert "não encontrado" in result
