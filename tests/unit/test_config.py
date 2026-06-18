import pytest

from smith.core.config import Config, describe_provider_selection, resolve_provider
from smith.core.exceptions import ConfigurationError


def test_resolve_provider_openai_default(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("SMITH_LLM_PROVIDER", raising=False)
    config = Config.load(load_env=False)
    assert resolve_provider(config) == "openai"


def test_resolve_provider_deepseek_fallback(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.delenv("SMITH_LLM_PROVIDER", raising=False)
    config = Config.load(load_env=False)
    assert resolve_provider(config) == "deepseek"


def test_resolve_provider_override(monkeypatch):
    monkeypatch.setenv("SMITH_LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    config = Config.load(load_env=False)
    assert resolve_provider(config) == "deepseek"


def test_resolve_provider_no_keys(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("SMITH_LLM_PROVIDER", raising=False)
    config = Config.load(load_env=False)
    with pytest.raises(ConfigurationError):
        resolve_provider(config)


def test_resolve_provider_override_missing_key(monkeypatch):
    monkeypatch.setenv("SMITH_LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config = Config.load(load_env=False)
    with pytest.raises(ConfigurationError):
        resolve_provider(config)


def test_describe_provider_selection_openai(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("SMITH_LLM_PROVIDER", raising=False)
    config = Config.load(load_env=False)
    provider, reason = describe_provider_selection(config)
    assert provider == "OpenAI"
    assert "OPENAI_API_KEY" in reason


def test_load_config_from_toml(tmp_path, monkeypatch):
    config_dir = tmp_path / ".smith"
    config_dir.mkdir()
    config_file = config_dir / "config.toml"
    config_file.write_text('deepseek_model = "custom-model"\n')
    monkeypatch.setenv("SMITH_CONFIG_PATH", str(config_file))
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    config = Config.load(load_env=False)
    assert config.config_file_loaded is True
    assert config.deepseek_model == "custom-model"
