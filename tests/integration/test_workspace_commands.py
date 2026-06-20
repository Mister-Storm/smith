import subprocess

from typer.testing import CliRunner

from smith.cli.app import app
from smith.services.chat import ChatService

runner = CliRunner()


def test_workspace_command(tmp_path, monkeypatch):
    from tests.helpers.workspace_fixture import init_workspace

    workspace = init_workspace(tmp_path, project_count=2)
    monkeypatch.chdir(workspace)

    result = runner.invoke(app, ["workspace"])
    assert result.exit_code == 0
    assert "Workspace Summary" in result.output
    assert "project-0" in result.output or "project-1" in result.output


def test_workspace_health_command(tmp_path, monkeypatch):
    from tests.helpers.workspace_fixture import init_workspace

    workspace = init_workspace(tmp_path, project_count=2)
    monkeypatch.chdir(workspace)

    result = runner.invoke(app, ["workspace-health"])
    assert result.exit_code == 0
    assert "Workspace Health" in result.output
    assert "Total Projects" in result.output


def test_refresh_and_workspace_context(tmp_path, monkeypatch):
    from tests.helpers.workspace_fixture import init_workspace

    workspace = init_workspace(tmp_path, project_count=2)
    monkeypatch.chdir(workspace)

    refresh = runner.invoke(app, ["refresh-workspace-context"])
    assert refresh.exit_code == 0
    assert "Stored at" in refresh.output

    show = runner.invoke(app, ["workspace-context"])
    assert show.exit_code == 0
    assert "Workspace Summary" in show.output


def test_workspace_no_projects(tmp_path, monkeypatch):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.chdir(empty)

    result = runner.invoke(app, ["workspace"])
    assert result.exit_code == 1
    assert "No projects were detected" in result.output


def test_workspace_context_missing(tmp_path, monkeypatch):
    empty = tmp_path / "nocache"
    empty.mkdir()
    (empty / "pyproject.toml").write_text("[project]\nname='x'\n")
    subprocess.run(["git", "init"], cwd=empty, check=True, capture_output=True)
    monkeypatch.chdir(empty)

    result = runner.invoke(app, ["workspace-context"])
    assert result.exit_code == 1
    assert "No workspace context found" in result.output


def test_chat_workspace_slash(tmp_path, fake_llm, memory_service, config_with_openai):
    from tests.helpers.workspace_fixture import init_workspace

    workspace = init_workspace(tmp_path, project_count=2)
    service = ChatService(fake_llm, memory_service, config_with_openai, workspace=workspace)
    result = service._handle_slash_command("/workspace")
    assert "Workspace Summary" in result
    assert "Execution time:" in result


def test_chat_single_project_warning(tmp_path, fake_llm, memory_service, config_with_openai):
    from tests.helpers.workspace_fixture import init_single_project_workspace

    workspace = init_single_project_workspace(tmp_path)
    service = ChatService(fake_llm, memory_service, config_with_openai, workspace=workspace)
    result = service._handle_slash_command("/workspace")
    assert "single project" in result.lower()
