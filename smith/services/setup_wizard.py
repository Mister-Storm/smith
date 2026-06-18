import os
from pathlib import Path

import typer

from smith.core.config import Config, get_smith_home, resolve_provider
from smith.memory.db import get_connection


def _env_key_for_provider(provider: str) -> str:
    return "OPENAI_API_KEY" if provider == "openai" else "DEEPSEEK_API_KEY"


def _write_env_sh(provider: str, api_key: str) -> Path:
    smith_home = get_smith_home()
    smith_home.mkdir(parents=True, exist_ok=True)
    env_path = smith_home / "env.sh"
    env_var = _env_key_for_provider(provider)

    existing = env_path.read_text(encoding="utf-8") if env_path.is_file() else ""
    export_line = f'export {env_var}="{api_key}"'

    if env_var in existing:
        lines = []
        for line in existing.splitlines():
            if line.startswith(f"export {env_var}="):
                lines.append(export_line)
            else:
                lines.append(line)
        content = "\n".join(lines) + "\n"
    else:
        header = "# Smith environment variables — source this file: source ~/.smith/env.sh\n"
        content = existing + "\n" if existing and not existing.endswith("\n") else existing
        if not content:
            content = header
        elif "# Smith environment" not in content:
            content = header + content
        content = content.rstrip() + "\n" + export_line + "\n"

    env_path.write_text(content, encoding="utf-8")
    env_path.chmod(0o600)
    return env_path


def _init_memory_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(db_path)
    conn.close()


def run_setup_wizard(*, configure_key: bool = True) -> Config:
    """Interactive setup. Saves non-secret config to TOML; keys go to env.sh only."""
    typer.echo("Welcome to Smith setup.\n")

    provider = typer.prompt("Select provider (openai/deepseek)", default="openai").lower()
    if provider not in ("openai", "deepseek"):
        provider = "openai"

    config = Config.load()
    config.llm_provider = provider

    if configure_key:
        env_var = _env_key_for_provider(provider)
        if not os.environ.get(env_var, "").strip():
            api_key = typer.prompt(f"Enter {env_var}", hide_input=True)
            if api_key.strip():
                env_path = _write_env_sh(provider, api_key.strip())
                os.environ[env_var] = api_key.strip()
                typer.echo(f"\nAPI key saved to {_display_path(env_path)} (not in config.toml).")
                typer.echo(f"Add to your shell: source {_display_path(env_path)}")
            else:
                typer.echo(
                    f"\nNo key entered. Set {env_var} in your environment before using Smith."
                )
        else:
            typer.echo(f"\n{env_var} already set in environment.")

    _init_memory_db(config.db_path)
    config.save()

    typer.echo(f"\nConfiguration saved to {_display_path(config.config_file_path)}")
    typer.echo("Run `smith doctor` to verify your installation.\n")

    return Config.load()


def _display_path(path: Path) -> str:
    home = Path.home()
    try:
        return f"~/{path.relative_to(home)}"
    except ValueError:
        return str(path)


def ensure_provider_configured(config: Config) -> Config:
    """Used by smith chat when keys are missing — interactive setup only."""
    try:
        resolve_provider(config)
        return config
    except Exception:
        typer.echo("Smith is not configured yet. Let's set it up.\n")
        return run_setup_wizard(configure_key=True)
