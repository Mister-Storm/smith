import pytest

from smith.core.config import (
    DEEPSEEK_V4_FLASH,
    DEEPSEEK_V4_PRO,
    Config,
    normalize_deepseek_model,
    resolve_deepseek_model_choice,
)
from smith.core.exceptions import ConfigurationError


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("deepseek-v4-flash", DEEPSEEK_V4_FLASH),
        ("deepseek-v4-pro", DEEPSEEK_V4_PRO),
        ("flash", DEEPSEEK_V4_FLASH),
        ("pro", DEEPSEEK_V4_PRO),
        ("1", DEEPSEEK_V4_FLASH),
        ("2", DEEPSEEK_V4_PRO),
        ("deepseek-chat", DEEPSEEK_V4_FLASH),
        ("deepseek-reasoner", DEEPSEEK_V4_FLASH),
    ],
)
def test_resolve_deepseek_model_choice(raw, expected):
    assert resolve_deepseek_model_choice(raw) == expected


def test_resolve_deepseek_model_choice_invalid():
    with pytest.raises(ConfigurationError, match="Unknown DeepSeek model"):
        resolve_deepseek_model_choice("deepseek-v3")


def test_normalize_deepseek_model_passthrough_custom():
    assert normalize_deepseek_model("custom-experimental") == "custom-experimental"


def test_load_config_normalizes_legacy_deepseek_model(tmp_path, monkeypatch):
    config_dir = tmp_path / ".smith"
    config_dir.mkdir()
    config_file = config_dir / "config.toml"
    config_file.write_text('deepseek_model = "deepseek-chat"\n')
    monkeypatch.setenv("SMITH_CONFIG_PATH", str(config_file))
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    config = Config.load(load_env=False)
    assert config.deepseek_model == DEEPSEEK_V4_FLASH


def test_load_config_deepseek_model_from_env(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_MODEL", "pro")
    config = Config.load(load_env=False)
    assert config.deepseek_model == DEEPSEEK_V4_PRO
