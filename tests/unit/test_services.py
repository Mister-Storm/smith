from unittest.mock import patch

from smith.services.chat import ChatService
from tests.helpers.git_repo import git_run


def test_chat_slash_duplicates(tmp_path, fake_llm, memory_service, config_with_openai):
    (tmp_path / "a.txt").write_text("dup")
    (tmp_path / "b.txt").write_text("dup")

    service = ChatService(fake_llm, memory_service, config_with_openai)
    result = service._handle_slash_command(f"/duplicates {tmp_path}")

    assert "Group 1" in result
    assert "Execution time:" in result


def test_chat_slash_unknown(fake_llm, memory_service, config_with_openai):
    service = ChatService(fake_llm, memory_service, config_with_openai)
    result = service._handle_slash_command("/unknown /path")
    assert "Unknown command" in result


def test_chat_slash_organize_dry_run(tmp_path, fake_llm, memory_service, config_with_openai):
    (tmp_path / "file.txt").write_text("hi")
    service = ChatService(fake_llm, memory_service, config_with_openai)
    result = service._handle_slash_command(f"/organize --dry-run {tmp_path}")
    assert "dry-run" in result


def test_chat_slash_context(tmp_path, fake_llm, memory_service, config_with_openai):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "build.gradle.kts").write_text('plugins { kotlin("jvm") }')
    (project / "Main.kt").write_text("fun main() {}")
    from smith.services.project_context import ProjectContextService

    service_ctx = ProjectContextService()
    service_ctx.refresh(project)

    service = ChatService(fake_llm, memory_service, config_with_openai, workspace=project)
    result = service._handle_slash_command("/context")
    assert "Project: proj" in result


def test_chat_context_injection(fake_llm, memory_service, config_with_openai, tmp_path):
    project = tmp_path / "app"
    project.mkdir()
    (project / "build.gradle.kts").write_text('plugins { kotlin("jvm") }')
    (project / "App.kt").write_text("class App\n")
    from smith.services.project_context import ProjectContextService

    ProjectContextService().refresh(project)

    service = ChatService(fake_llm, memory_service, config_with_openai, workspace=project)
    session_id = memory_service.start_session()
    memory_service.add_message(session_id, "user", "hello")
    service._handle_chat(session_id, "hello")

    assert len(fake_llm.calls) == 1
    prompt = fake_llm.calls[0][0]
    assert "Current Project Context" in prompt
    assert "app" in prompt.lower() or "kotlin" in prompt.lower()


def test_chat_slash_refresh_context(tmp_path, fake_llm, memory_service, config_with_openai):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "build.gradle.kts").write_text('plugins { kotlin("jvm") }')
    (project / "Main.kt").write_text("fun main() {}\n")

    service = ChatService(fake_llm, memory_service, config_with_openai, workspace=project)
    result = service._handle_slash_command("/refresh-context")
    assert "Project: proj" in result
    assert service._project_context is not None


def test_chat_slash_analyze_structure_only(tmp_path, fake_llm, memory_service, config_with_openai):
    (tmp_path / "Main.kt").write_text("fun main() {}")
    service = ChatService(fake_llm, memory_service, config_with_openai)
    result = service._handle_slash_command(f"/analyze {tmp_path} --structure-only")
    assert "# Project Context" in result
    assert len(fake_llm.calls) == 0


def test_chat_normal_message(fake_llm, memory_service, config_with_openai):
    session_id = memory_service.start_session()
    memory_service.add_message(session_id, "user", "hello")

    service = ChatService(fake_llm, memory_service, config_with_openai)
    result = service._handle_chat(session_id, "hello")

    assert "fake response" in result
    assert "Provider:" in result
    assert len(fake_llm.calls) == 1


def test_chat_slash_git_summary(git_repo, fake_llm, memory_service, config_with_openai):
    (git_repo / "changes.py").write_text("x = 1\n")
    git_run(git_repo, "checkout", "-b", "feat/git-test")
    service = ChatService(fake_llm, memory_service, config_with_openai, workspace=git_repo)
    result = service._handle_slash_command("/git-summary")
    assert "feat/git-test" in result
    assert "Assessment" in result
    assert "Execution time:" in result


def test_chat_slash_git_health(git_repo, fake_llm, memory_service, config_with_openai):
    service = ChatService(fake_llm, memory_service, config_with_openai, workspace=git_repo)
    result = service._handle_slash_command("/git-health")
    assert "Repository" in result
    assert "Recent Activity" in result


def test_chat_slash_git_changes(git_repo, fake_llm, memory_service, config_with_openai):
    (git_repo / "changes.py").write_text("x = 1\n")
    service = ChatService(fake_llm, memory_service, config_with_openai, workspace=git_repo)
    result = service._handle_slash_command("/git-changes")
    assert "changes.py" in result


def test_chat_slash_commit_message(git_repo, fake_llm, memory_service, config_with_openai):
    test_dir = git_repo / "tests"
    test_dir.mkdir(parents=True)
    (test_dir / "test_a.py").write_text("def test_a(): pass\n")
    service = ChatService(fake_llm, memory_service, config_with_openai, workspace=git_repo)
    result = service._handle_slash_command("/commit-message")
    assert "Suggested Commits" in result


def test_chat_slash_release_notes(git_repo, fake_llm, memory_service, config_with_openai):
    git_run(git_repo, "commit", "--allow-empty", "-m", "docs: update readme")
    service = ChatService(fake_llm, memory_service, config_with_openai, workspace=git_repo)
    result = service._handle_slash_command("/release-notes")
    assert "Release Notes" in result


def test_chat_slash_git_not_repo(tmp_path, fake_llm, memory_service, config_with_openai):
    service = ChatService(fake_llm, memory_service, config_with_openai, workspace=tmp_path)
    result = service._handle_slash_command("/git-summary")
    assert "not a Git repository" in result


def test_doctor_healthy(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("SMITH_DB_PATH", str(tmp_path / "mem.db"))
    monkeypatch.setenv("SMITH_CONFIG_PATH", str(tmp_path / "missing.toml"))
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / "smith_home"))

    from smith.services.doctor import format_doctor_report, run_doctor

    report = run_doctor(test_provider=False)
    assert report.exit_code in (0, 1)
    text = format_doctor_report(report)
    assert "Smith Doctor Report" in text
    assert "OpenAI API Key: Configured" in text


def test_doctor_no_provider(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("SMITH_DB_PATH", str(tmp_path / "mem.db"))

    from smith.services.doctor import run_doctor

    report = run_doctor(test_provider=False)
    assert report.exit_code == 2


def test_doctor_connectivity_mock(monkeypatch, tmp_path, fake_llm):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("SMITH_DB_PATH", str(tmp_path / "mem.db"))
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / "smith_home"))

    from smith.services.doctor import CheckStatus, run_doctor

    with patch("smith.services.doctor.get_llm_provider", return_value=fake_llm):
        report = run_doctor(test_provider=True)

    assert report.connectivity is not None
    assert report.connectivity.status == CheckStatus.OK
    assert "Latency" in report.connectivity.lines[2]


def test_doctor_connectivity_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("SMITH_DB_PATH", str(tmp_path / "mem.db"))
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / "smith_home"))

    from smith.services.doctor import CheckStatus, run_doctor

    class FailingLLM:
        name = "Fake"

        def generate(self, prompt, *, system=None):
            raise RuntimeError("connection refused")

    with patch("smith.services.doctor.get_llm_provider", return_value=FailingLLM()):
        report = run_doctor(test_provider=True)

    assert report.connectivity.status == CheckStatus.WARN
    assert report.exit_code == 1
