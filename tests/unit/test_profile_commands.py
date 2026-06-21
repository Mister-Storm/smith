from typer.testing import CliRunner

from smith.cli.app import app

runner = CliRunner()


def test_profile_show_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    result = runner.invoke(app, ["profile", "show"])
    assert result.exit_code == 0
    assert "User Profile" in result.output


def test_profile_set_interest_and_goal(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    runner.invoke(app, ["profile", "set-interest", "drones"])
    runner.invoke(app, ["profile", "set-goal", "build-smith"])
    result = runner.invoke(app, ["profile", "show"])
    assert result.exit_code == 0
    assert "drones" in result.output
    assert "build-smith" in result.output


def test_profile_refresh(tmp_path, monkeypatch):
    from tests.helpers.workspace_fixture import init_workspace

    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    workspace = init_workspace(tmp_path, project_count=1)
    monkeypatch.chdir(workspace)
    runner.invoke(app, ["refresh-workspace-context"])
    project = workspace / "project-0"
    monkeypatch.chdir(project)
    runner.invoke(app, ["refresh-context"])

    monkeypatch.chdir(workspace)
    result = runner.invoke(app, ["profile", "refresh"])
    assert result.exit_code == 0
    assert "Stored at" in result.output


def test_profile_explain(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    result = runner.invoke(app, ["profile", "explain"])
    assert result.exit_code == 0
    assert "Profile Explanation" in result.output or "Explanation" in result.output


def test_profile_remove_interest(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    runner.invoke(app, ["profile", "set-interest", "drones"])
    result = runner.invoke(app, ["profile", "remove-interest", "drones"])
    assert result.exit_code == 0
    assert "drones" not in result.output or "—" in result.output
