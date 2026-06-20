from smith.core.config import Config, needs_setup
from smith.services.setup_wizard import run_setup_wizard


def test_needs_setup_without_keys(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    config = Config.load(load_env=False)
    assert needs_setup(config)


def test_needs_setup_with_keys(config_with_openai):
    assert not needs_setup(config_with_openai)


def test_config_save_no_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_CONFIG_PATH", str(tmp_path / "config.toml"))
    monkeypatch.setenv("SMITH_HOME", str(tmp_path))
    config = Config.load(load_env=False)
    config.llm_provider = "openai"
    config.db_path = tmp_path / "memory.db"
    config.save()

    content = (tmp_path / "config.toml").read_text()
    assert "smith_llm_provider" in content
    assert "openai_api_key" not in content.lower()
    assert "OPENAI_API_KEY" not in content


def test_setup_wizard_saves_deepseek_model(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_CONFIG_PATH", str(tmp_path / "config.toml"))
    monkeypatch.setenv("SMITH_HOME", str(tmp_path))
    monkeypatch.setenv("SMITH_DB_PATH", str(tmp_path / "memory.db"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    prompts = iter(["deepseek", "2"])
    monkeypatch.setattr("smith.services.setup_wizard.typer.prompt", lambda *a, **k: next(prompts))
    monkeypatch.setattr("smith.services.setup_wizard.typer.echo", lambda *a, **k: None)

    run_setup_wizard(configure_key=False)

    saved = (tmp_path / "config.toml").read_text()
    assert 'deepseek_model = "deepseek-v4-pro"' in saved


def test_setup_wizard_saves_config(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_CONFIG_PATH", str(tmp_path / "config.toml"))
    monkeypatch.setenv("SMITH_HOME", str(tmp_path))
    monkeypatch.setenv("SMITH_DB_PATH", str(tmp_path / "memory.db"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("smith.services.setup_wizard.typer.prompt", lambda *a, **k: "openai")
    monkeypatch.setattr("smith.services.setup_wizard.typer.echo", lambda *a, **k: None)

    run_setup_wizard(configure_key=False)

    assert (tmp_path / "config.toml").is_file()
    saved = (tmp_path / "config.toml").read_text()
    assert "smith_llm_provider" in saved
    assert "api_key" not in saved.lower()


def test_write_env_sh_no_config_toml(tmp_path, monkeypatch):
    from smith.services.setup_wizard import _write_env_sh

    monkeypatch.setenv("SMITH_HOME", str(tmp_path))
    env_path = _write_env_sh("openai", "sk-test-secret")
    content = env_path.read_text()
    assert "OPENAI_API_KEY" in content
    assert (tmp_path / "config.toml").exists() is False
