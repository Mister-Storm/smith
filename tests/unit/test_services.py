from unittest.mock import patch

from smith.services.chat import ChatService
from smith.services.doctor import CheckStatus, format_doctor_report, run_doctor


def test_chat_slash_duplicates(tmp_path, fake_llm, memory_service, config_with_openai):
    (tmp_path / "a.txt").write_text("dup")
    (tmp_path / "b.txt").write_text("dup")

    service = ChatService(fake_llm, memory_service, config_with_openai)
    result = service._handle_slash_command(f"/duplicates {tmp_path}")

    assert "Group 1" in result


def test_chat_slash_unknown(fake_llm, memory_service, config_with_openai):
    service = ChatService(fake_llm, memory_service, config_with_openai)
    result = service._handle_slash_command("/unknown /path")
    assert "Unknown command" in result


def test_chat_slash_organize_dry_run(tmp_path, fake_llm, memory_service, config_with_openai):
    (tmp_path / "file.txt").write_text("hi")
    service = ChatService(fake_llm, memory_service, config_with_openai)
    result = service._handle_slash_command(f"/organize --dry-run {tmp_path}")
    assert "dry-run" in result


def test_chat_normal_message(fake_llm, memory_service, config_with_openai):
    session_id = memory_service.start_session()
    memory_service.add_message(session_id, "user", "hello")

    service = ChatService(fake_llm, memory_service, config_with_openai)
    result = service._handle_chat(session_id, "hello")

    assert result == "fake response"
    assert len(fake_llm.calls) == 1


def test_doctor_healthy(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("SMITH_DB_PATH", str(tmp_path / "mem.db"))
    monkeypatch.setenv("SMITH_CONFIG_PATH", str(tmp_path / "missing.toml"))
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / "smith_home"))

    report = run_doctor(test_provider=False)
    assert report.exit_code in (0, 1)
    text = format_doctor_report(report)
    assert "Smith Doctor Report" in text
    assert "OpenAI API Key: Configured" in text


def test_doctor_no_provider(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("SMITH_DB_PATH", str(tmp_path / "mem.db"))

    report = run_doctor(test_provider=False)
    assert report.exit_code == 2


def test_doctor_connectivity_mock(monkeypatch, tmp_path, fake_llm):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("SMITH_DB_PATH", str(tmp_path / "mem.db"))
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / "smith_home"))

    with patch("smith.services.doctor.get_llm_provider", return_value=fake_llm):
        report = run_doctor(test_provider=True)

    assert report.connectivity is not None
    assert report.connectivity.status == CheckStatus.OK
    assert "Latency" in report.connectivity.lines[2]


def test_doctor_connectivity_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("SMITH_DB_PATH", str(tmp_path / "mem.db"))
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / "smith_home"))

    class FailingLLM:
        name = "Fake"

        def generate(self, prompt, *, system=None):
            raise RuntimeError("connection refused")

    with patch("smith.services.doctor.get_llm_provider", return_value=FailingLLM()):
        report = run_doctor(test_provider=True)

    assert report.connectivity.status == CheckStatus.WARN
    assert report.exit_code == 1
