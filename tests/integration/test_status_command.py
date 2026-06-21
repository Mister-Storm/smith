import re
import time

from typer.testing import CliRunner

from smith.cli.app import app

runner = CliRunner()


def test_status_command_with_caches(tmp_path, monkeypatch):
    from tests.helpers.workspace_fixture import init_workspace

    workspace = init_workspace(tmp_path, project_count=2)
    monkeypatch.chdir(workspace)

    runner.invoke(app, ["refresh-workspace-context"])
    runner.invoke(app, ["health"], catch_exceptions=False)

    project = workspace / "project-0"
    monkeypatch.chdir(project)
    runner.invoke(app, ["refresh-context"])

    started = time.perf_counter()
    result = runner.invoke(app, ["status"])
    elapsed = time.perf_counter() - started

    assert result.exit_code == 0
    assert "Smith Status" in result.output
    assert "Environment" in result.output
    assert "Cache Freshness" in result.output
    assert "Git Status" in result.output
    assert "User Context" in result.output
    assert elapsed < 2.0


def test_status_missing_caches_graceful(tmp_path, monkeypatch):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.chdir(empty)

    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "Not cached" in result.output or "Missing" in result.output


def test_status_with_user_profile(tmp_path, monkeypatch):
    from tests.helpers.workspace_fixture import init_workspace

    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    workspace = init_workspace(tmp_path, project_count=1)
    monkeypatch.chdir(workspace)
    runner.invoke(app, ["profile", "set-interest", "drones"])
    runner.invoke(app, ["profile", "refresh"])
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "User Context" in result.output
    assert "Completeness" in result.output


def test_status_execution_time_in_footer(tmp_path, monkeypatch):
    from tests.helpers.workspace_fixture import init_workspace

    workspace = init_workspace(tmp_path, project_count=1)
    monkeypatch.chdir(workspace)

    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "Execution time:" in result.output
    match = re.search(r"Execution time: (\d+)ms", result.output)
    if match:
        assert int(match.group(1)) < 2000
