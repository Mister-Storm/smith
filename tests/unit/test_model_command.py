import pytest
from typer.testing import CliRunner

from smith.cli.app import app
from smith.core.config import DEEPSEEK_V4_PRO


@pytest.fixture
def runner():
    return CliRunner()


def test_model_command_sets_deepseek_model(tmp_path, monkeypatch, runner):
    config_file = tmp_path / "config.toml"
    monkeypatch.setenv("SMITH_CONFIG_PATH", str(config_file))
    monkeypatch.setenv("SMITH_LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")

    result = runner.invoke(app, ["model", "pro"])

    assert result.exit_code == 0, result.stdout
    assert DEEPSEEK_V4_PRO in result.stdout
    assert f'deepseek_model = "{DEEPSEEK_V4_PRO}"' in config_file.read_text()


def test_model_command_requires_deepseek_provider(tmp_path, monkeypatch, runner):
    config_file = tmp_path / "config.toml"
    monkeypatch.setenv("SMITH_CONFIG_PATH", str(config_file))
    monkeypatch.setenv("SMITH_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    result = runner.invoke(app, ["model", "flash"])

    assert result.exit_code == 1
    assert "only available for the DeepSeek provider" in result.stdout
