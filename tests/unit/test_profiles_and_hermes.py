"""Tests for profiles and Hermes integration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from smith.core.config import (
    Config,
    get_config_file_path,
    get_smith_home,
    resolve_profile_name,
)


class TestProfileResolution:
    def test_should_default_to_default(self) -> None:
        assert resolve_profile_name() == "default"
        assert resolve_profile_name(None) == "default"

    def test_should_use_override(self) -> None:
        assert resolve_profile_name("work") == "work"

    def test_should_read_from_env(self, monkeypatch) -> None:
        monkeypatch.setenv("SMITH_PROFILE", "env-profile")
        assert resolve_profile_name() == "env-profile"
        assert resolve_profile_name("cli-override") == "cli-override"  # override wins


class TestSmithHomeWithProfile:
    def test_should_return_default_path_without_profile(self) -> None:
        home = get_smith_home()
        assert home.name == ".smith"
        assert "profiles" not in str(home)

    def test_should_return_profiles_subdir_for_named_profile(self) -> None:
        home = get_smith_home("work")
        assert "profiles" in str(home)
        assert home.name == "work"

    def test_should_ignore_default_profile(self) -> None:
        home = get_smith_home("default")
        assert "profiles" not in str(home)

    def test_should_respect_env_override(self, monkeypatch) -> None:
        monkeypatch.setenv("SMITH_HOME", "/custom/smith")
        home = get_smith_home("work")
        assert str(home) == "/custom/smith/profiles/work"


class TestConfigFilePathWithProfile:
    def test_should_use_profile_path(self) -> None:
        path = get_config_file_path("custom")
        assert "profiles/custom" in str(path)
        assert path.name == "config.toml"

    def test_should_use_default_path(self) -> None:
        path = get_config_file_path("default")
        assert "profiles" not in str(path)
        assert path.name == "config.toml"


class TestConfigLoadWithProfile:
    def test_should_load_from_profile_dir(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("SMITH_HOME", str(tmp_path))
        profile_dir = tmp_path / "profiles" / "work"
        profile_dir.mkdir(parents=True)
        (profile_dir / "config.toml").write_text(
            'smith_llm_provider = "deepseek"\ndeepseek_model = "deepseek-v4-pro"\n'
        )

        config = Config.load(profile_name="work")
        assert config.llm_provider == "deepseek"
        assert config.deepseek_model == "deepseek-v4-pro"
        assert str(config.db_path).startswith(str(profile_dir))

    def test_should_not_mix_with_default_profile(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("SMITH_HOME", str(tmp_path))
        default_dir = tmp_path
        (default_dir / "config.toml").write_text('smith_llm_provider = "openai"\n')
        profile_dir = tmp_path / "profiles" / "secret"
        profile_dir.mkdir(parents=True)
        (profile_dir / "config.toml").write_text('smith_llm_provider = "deepseek"\n')

        default_config = Config.load(profile_name="default")
        secret_config = Config.load(profile_name="secret")

        assert default_config.llm_provider == "openai"
        assert secret_config.llm_provider == "deepseek"


class TestHermesIntegration:
    def test_should_return_error_when_no_args(self) -> None:
        from smith.services.slash_commands import _handle_hermes

        service = MagicMock()
        result = _handle_hermes(service, [])
        assert not result.success
        assert "Usage:" in result.message

    def test_should_execute_hermes_task(self) -> None:
        from smith.tools.hermes_integration import run_hermes_task

        with (
            patch("smith.tools.hermes_integration.subprocess.run") as mock_run,
            patch("smith.tools.hermes_integration._is_hermes_installed", return_value=True),
        ):
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Task completed."
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            result = run_hermes_task("create a test file")
            assert result.success
            assert "Task completed" in result.message

    def test_should_report_hermes_failure(self) -> None:
        from smith.tools.hermes_integration import run_hermes_task

        with (
            patch("smith.tools.hermes_integration.subprocess.run") as mock_run,
            patch("smith.tools.hermes_integration._is_hermes_installed", return_value=True),
        ):
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "Error: something broke"
            mock_run.return_value = mock_result

            result = run_hermes_task("do something")
            assert not result.success
            assert "exit code 1" in result.message

    def test_should_report_when_hermes_not_installed(self) -> None:
        from smith.tools.hermes_integration import run_hermes_task

        with patch("smith.tools.hermes_integration._is_hermes_installed", return_value=False):
            result = run_hermes_task("anything")
            assert not result.success
            assert "not found" in result.message.lower()
