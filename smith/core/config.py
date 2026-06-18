import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from smith.core.exceptions import ConfigurationError

MIN_PYTHON_VERSION = (3, 12)


def get_smith_home() -> Path:
    env_path = os.environ.get("SMITH_HOME")
    if env_path:
        return Path(env_path).expanduser()
    return Path("~/.smith").expanduser()


def get_config_file_path() -> Path:
    env_path = os.environ.get("SMITH_CONFIG_PATH")
    if env_path:
        return Path(env_path).expanduser()
    return get_smith_home() / "config.toml"


def _load_config_file(path: Path) -> dict:
    if not path.is_file():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def is_key_set(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


@dataclass
class Config:
    openai_api_key: str = ""
    deepseek_api_key: str = ""
    llm_provider: str = ""
    db_path: Path = field(default_factory=lambda: Path("~/.smith/memory.db").expanduser())
    openai_model: str = "gpt-4o-mini"
    deepseek_model: str = "deepseek-chat"
    config_file_path: Path = field(default_factory=get_config_file_path)
    config_file_loaded: bool = False

    @classmethod
    def load(cls, *, load_env: bool = True) -> "Config":
        config_path = get_config_file_path()
        file_data = _load_config_file(config_path)
        config_file_loaded = config_path.is_file()

        if load_env and not os.environ.get("SMITH_SKIP_DOTENV"):
            load_dotenv()
            if config_path.parent.exists():
                env_in_smith = config_path.parent / ".env"
                if env_in_smith.is_file():
                    load_dotenv(env_in_smith)

        toml_keys = {
            "OPENAI_API_KEY": "openai_api_key",
            "DEEPSEEK_API_KEY": "deepseek_api_key",
            "SMITH_LLM_PROVIDER": "smith_llm_provider",
            "OPENAI_MODEL": "openai_model",
            "DEEPSEEK_MODEL": "deepseek_model",
            "SMITH_DB_PATH": "db_path",
        }

        def _get(key: str, default: str = "") -> str:
            env_val = os.environ.get(key, "").strip()
            if env_val:
                return env_val
            toml_key = toml_keys.get(key, key.lower())
            file_val = file_data.get(toml_key) or file_data.get(key.lower()) or file_data.get(key)
            if file_val is not None:
                return str(file_val).strip()
            return default

        db_path_str = _get("SMITH_DB_PATH") or file_data.get("db_path", "")
        default_db = Path("~/.smith/memory.db").expanduser()
        db_path = Path(db_path_str).expanduser() if db_path_str else default_db

        return cls(
            openai_api_key=_get("OPENAI_API_KEY"),
            deepseek_api_key=_get("DEEPSEEK_API_KEY"),
            llm_provider=_get("SMITH_LLM_PROVIDER").lower(),
            db_path=db_path,
            openai_model=_get("OPENAI_MODEL", "gpt-4o-mini"),
            deepseek_model=_get("DEEPSEEK_MODEL", "deepseek-chat"),
            config_file_path=config_path,
            config_file_loaded=config_file_loaded,
        )


def resolve_provider(config: Config) -> str:
    if config.llm_provider:
        provider = config.llm_provider
        if provider == "openai":
            if not config.openai_api_key:
                raise ConfigurationError("SMITH_LLM_PROVIDER=openai but OPENAI_API_KEY is not set")
            return "openai"
        if provider == "deepseek":
            if not config.deepseek_api_key:
                raise ConfigurationError(
                    "SMITH_LLM_PROVIDER=deepseek but DEEPSEEK_API_KEY is not set"
                )
            return "deepseek"
        raise ConfigurationError(f"Unknown SMITH_LLM_PROVIDER: {config.llm_provider}")

    if config.openai_api_key:
        return "openai"
    if config.deepseek_api_key:
        return "deepseek"
    raise ConfigurationError("No LLM provider configured. Set OPENAI_API_KEY or DEEPSEEK_API_KEY.")


def describe_provider_selection(config: Config) -> tuple[str, str]:
    try:
        provider = resolve_provider(config)
    except ConfigurationError as exc:
        return "None", str(exc)

    if config.llm_provider:
        reason = f"SMITH_LLM_PROVIDER={config.llm_provider} override"
    elif provider == "openai":
        reason = "OPENAI_API_KEY is set (default selection)"
    else:
        reason = "DEEPSEEK_API_KEY is set (OpenAI key not configured)"

    display_names = {"openai": "OpenAI", "deepseek": "DeepSeek"}
    return display_names.get(provider, provider.capitalize()), reason
