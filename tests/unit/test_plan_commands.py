from typer.testing import CliRunner

from smith.cli.app import app

runner = CliRunner()


def test_plan_status_command(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["plan-status"])
    assert result.exit_code == 0
    assert "Planning Readiness" in result.output


def test_plan_refresh_command(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["plan-refresh"])
    assert result.exit_code == 0
    assert "Planning Explanation" in result.output or "Knowns" in result.output


def test_plan_explain_command(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["plan", "explain"])
    assert result.exit_code == 0
    assert "Knowns" in result.output or "Planning Explanation" in result.output


def test_plan_goal_command(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["plan", "build", "api"])
    assert result.exit_code == 0
    assert "Goal:" in result.output


def test_plan_requires_goal(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["plan"])
    assert result.exit_code != 0
