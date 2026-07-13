"""Tests for doctor --deep and history compression."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from smith.services.doctor import DoctorReport, _check_deep_connectivity
from smith.services.history_compression import compress_session_history


class TestDeepConnectivity:
    def test_should_skip_when_provider_unavailable(self) -> None:
        from smith.core.exceptions import ConfigurationError

        config = MagicMock()
        with patch(
            "smith.services.doctor.get_llm_provider", side_effect=ConfigurationError("no key")
        ):
            result = _check_deep_connectivity(config)
            assert "Provider: None" in result.lines[0]
            assert "SKIPPED" in " ".join(result.lines)

    def test_should_report_basic_and_structured_and_tool_calls(self) -> None:
        config = MagicMock()
        provider = MagicMock()
        provider.name = "TestProvider"
        provider.generate.return_value = "ok"
        provider.generate_structured.return_value = {"test": True}

        tool_resp = MagicMock()
        tool_resp.tool_calls = (MagicMock(),)
        tool_resp.content = ""
        tool_resp.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        provider.generate_with_tools.return_value = tool_resp

        with patch("smith.services.doctor.get_llm_provider", return_value=provider):
            result = _check_deep_connectivity(config)

        lines = "\n".join(result.lines)
        assert "TestProvider" in lines
        assert "Basic: OK" in lines
        assert "Structured: OK" in lines
        assert "Tool Calling: OK" in lines
        assert "Token Usage" in lines

    def test_should_report_mismatch_on_bad_content(self) -> None:
        config = MagicMock()
        provider = MagicMock()
        provider.name = "TestProvider"
        provider.generate.return_value = "wrong response"
        provider.generate_structured.return_value = {"test": False}
        provider.generate_with_tools.return_value = MagicMock(
            tool_calls=(), content="no tool call", usage=None
        )

        with patch("smith.services.doctor.get_llm_provider", return_value=provider):
            result = _check_deep_connectivity(config)

        lines = "\n".join(result.lines)
        assert "CONTENT_MISMATCH" in lines or "FAILED" in lines or "NO_TOOL_CALL" in lines

    def test_should_report_failed_on_exception(self) -> None:
        config = MagicMock()
        provider = MagicMock()
        provider.name = "TestProvider"
        provider.generate.side_effect = Exception("API error")
        provider.generate_structured.side_effect = Exception("structured error")
        provider.generate_with_tools.side_effect = Exception("tools error")

        with patch("smith.services.doctor.get_llm_provider", return_value=provider):
            result = _check_deep_connectivity(config)

        lines = "\n".join(result.lines)
        assert "Basic: FAILED" in lines
        assert "Structured: FAILED" in lines
        assert "Tool Calling: FAILED" in lines


class TestDoctorReportDeep:
    def test_should_include_deep_check_in_exit_code(self) -> None:
        report = DoctorReport(
            sections=[("Python", MagicMock(status="ok"))],
            deep_check=MagicMock(status="warn", lines=[]),
        )
        assert report.exit_code == 1  # warn

    def test_should_prioritize_critical_over_warn(self) -> None:
        report = DoctorReport(
            sections=[("Python", MagicMock(status="critical"))],
            deep_check=MagicMock(status="warn", lines=[]),
        )
        assert report.exit_code == 2


class TestHistoryCompression:
    def test_should_skip_when_below_threshold(self) -> None:
        memory = MagicMock()
        memory.count_session_messages.return_value = 5
        result = compress_session_history("s1", memory=memory, llm=MagicMock())
        assert result is False

    def test_should_compress_when_above_threshold(self) -> None:
        memory = MagicMock()
        memory.count_session_messages.return_value = 35

        # 35 messages: 25 old + 10 recent
        old_msgs = [("user", f"msg_{i}") for i in range(25)]
        recent_msgs = [("user", f"recent_{i}") for i in range(10)]
        memory.get_all_session_messages.return_value = old_msgs + recent_msgs

        llm = MagicMock()
        llm.generate.return_value = "Compressed summary of the conversation."

        result = compress_session_history("s1", memory=memory, llm=llm)

        assert result is True
        memory.replace_old_messages.assert_called_once_with(
            "s1", keep_count=10, summary_content="Compressed summary of the conversation."
        )

    def test_should_not_compress_when_not_many_messages(self) -> None:
        memory = MagicMock()
        memory.count_session_messages.return_value = 12
        memory.get_all_session_messages.return_value = [("user", "hi")] * 12

        result = compress_session_history("s1", memory=memory, llm=MagicMock())
        assert result is False  # 12 <= keep_latest(10) + threshold consideration

    def test_should_return_false_on_llm_failure(self) -> None:
        memory = MagicMock()
        memory.count_session_messages.return_value = 35
        memory.get_all_session_messages.return_value = [("user", "x")] * 35

        llm = MagicMock()
        llm.generate.side_effect = Exception("LLM error")

        result = compress_session_history("s1", memory=memory, llm=llm)
        assert result is False


class TestMemoryServiceHistory:
    def test_should_count_session_messages(self, tmp_path: Path) -> None:
        from smith.memory.service import MemoryService

        svc = MemoryService(tmp_path / "test.db")
        sid = svc.start_session()
        svc.add_message(sid, "user", "hello")
        svc.add_message(sid, "assistant", "world")
        assert svc.count_session_messages(sid) == 2

    def test_should_get_all_session_messages(self, tmp_path: Path) -> None:
        from smith.memory.service import MemoryService

        svc = MemoryService(tmp_path / "test.db")
        sid = svc.start_session()
        svc.add_message(sid, "user", "a")
        svc.add_message(sid, "assistant", "b")
        msgs = svc.get_all_session_messages(sid)
        assert msgs == [("user", "a"), ("assistant", "b")]

    def test_should_replace_old_messages(self, tmp_path: Path) -> None:
        from smith.memory.service import MemoryService

        svc = MemoryService(tmp_path / "test.db")
        sid = svc.start_session()
        for i in range(15):
            svc.add_message(sid, "user", f"msg_{i}")

        svc.replace_old_messages(sid, keep_count=5, summary_content="summary text")

        msgs = svc.get_all_session_messages(sid)
        # Should have 1 summary + 5 recent
        assert len(msgs) == 6
        # Summary should be present somewhere in the results
        summary_found = any("summary" in content for _, content in msgs)
        assert summary_found

    def test_should_not_delete_when_fewer_than_keep(self, tmp_path: Path) -> None:
        from smith.memory.service import MemoryService

        svc = MemoryService(tmp_path / "test.db")
        sid = svc.start_session()
        svc.add_message(sid, "user", "only one")

        svc.replace_old_messages(sid, keep_count=5, summary_content="summary")

        # Should not delete anything when there's only 1 message and keep=5
        msgs = svc.get_all_session_messages(sid)
        assert len(msgs) == 2  # original + summary
