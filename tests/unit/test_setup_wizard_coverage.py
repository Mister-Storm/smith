"""Tests for setup_wizard coverage gaps."""

from __future__ import annotations

from pathlib import Path

from smith.services.setup_wizard import (
    _display_path,
    _init_memory_db,
    _write_env_sh,
    ensure_provider_configured,
)


class TestWriteEnvSh:
    def test_should_write_new_env_file_for_openai(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("SMITH_HOME", str(tmp_path))
        env_path = _write_env_sh("openai", "sk-test")
        content = env_path.read_text()
        assert "OPENAI_API_KEY" in content
        assert "sk-test" in content
        assert content.startswith("# Smith")

    def test_should_write_new_env_file_for_deepseek(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("SMITH_HOME", str(tmp_path))
        env_path = _write_env_sh("deepseek", "sk-ds-test")
        content = env_path.read_text()
        assert "DEEPSEEK_API_KEY" in content
        assert "sk-ds-test" in content

    def test_should_update_existing_env_var(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("SMITH_HOME", str(tmp_path))
        _write_env_sh("openai", "old-key")
        env_path = _write_env_sh("openai", "new-key")
        content = env_path.read_text()
        assert "OLD-KEY" not in content.upper()  # old value replaced
        assert "new-key" in content

    def test_should_add_second_provider(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("SMITH_HOME", str(tmp_path))
        _write_env_sh("openai", "sk-openai")
        _write_env_sh("deepseek", "sk-deepseek")
        content = (tmp_path / "env.sh").read_text()
        assert "OPENAI_API_KEY" in content
        assert "DEEPSEEK_API_KEY" in content

    def test_should_set_secure_permissions(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("SMITH_HOME", str(tmp_path))
        env_path = _write_env_sh("openai", "sk-test")
        assert env_path.stat().st_mode & 0o777 == 0o600


class TestInitMemoryDb:
    def test_should_create_db_file(self, tmp_path: Path) -> None:
        db_path = tmp_path / "subdir" / "memory.db"
        _init_memory_db(db_path)
        assert db_path.is_file()

    def test_should_create_parent_directory(self, tmp_path: Path) -> None:
        db_path = tmp_path / "nested" / "deep" / "memory.db"
        _init_memory_db(db_path)
        assert db_path.parent.is_dir()


class TestDisplayPath:
    def test_should_show_home_relative(self) -> None:
        home = Path.home()
        path = home / "test" / "file.txt"
        result = _display_path(path)
        assert result.startswith("~/")

    def test_should_show_absolute_when_outside_home(self) -> None:
        path = Path("/opt/smith/config.toml")
        result = _display_path(path)
        assert result == "/opt/smith/config.toml"

    def test_should_show_absolute_for_tmp(self, tmp_path: Path) -> None:
        result = _display_path(tmp_path)
        assert result == str(tmp_path)


class TestEnsureProviderConfigured:
    def test_should_return_config_when_already_configured(self, config_with_openai) -> None:
        result = ensure_provider_configured(config_with_openai)
        assert result is config_with_openai

    def test_should_run_setup_when_missing_keys(self, monkeypatch, tmp_path) -> None:
        from smith.core.config import Config

        monkeypatch.setenv("SMITH_CONFIG_PATH", str(tmp_path / "config.toml"))
        monkeypatch.setenv("SMITH_HOME", str(tmp_path))
        monkeypatch.setenv("SMITH_DB_PATH", str(tmp_path / "memory.db"))
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.setattr("smith.services.setup_wizard.typer.prompt", lambda *a, **k: "openai")
        monkeypatch.setattr("smith.services.setup_wizard.typer.echo", lambda *a, **k: None)

        config = Config.load(load_env=False)
        result = ensure_provider_configured(config)
        assert result.llm_provider == "openai"
