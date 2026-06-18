from typer.testing import CliRunner

from smith.cli.app import app

runner = CliRunner()


def test_version_command(config_with_openai, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "Smith" in result.output
    assert "Provider:" in result.output
    assert "Model:" in result.output


def test_version_not_configured(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "not configured" in result.output
    assert "smith setup" in result.output
