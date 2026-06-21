import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from smith.core.exceptions import ConfigurationError

MIN_PYTHON_VERSION = (3, 12)

DEEPSEEK_V4_FLASH = "deepseek-v4-flash"
DEEPSEEK_V4_PRO = "deepseek-v4-pro"
DEFAULT_DEEPSEEK_MODEL = DEEPSEEK_V4_FLASH

DEEPSEEK_MODEL_OPTIONS: dict[str, str] = {
    DEEPSEEK_V4_FLASH: "DeepSeek-V4-Flash — fast and economical",
    DEEPSEEK_V4_PRO: "DeepSeek-V4-Pro — highest quality",
}

_LEGACY_DEEPSEEK_MODELS = {
    "deepseek-chat": DEEPSEEK_V4_FLASH,
    "deepseek-reasoner": DEEPSEEK_V4_FLASH,
}

_DEEPSEEK_MODEL_ALIASES = {
    "v4-flash": DEEPSEEK_V4_FLASH,
    "flash": DEEPSEEK_V4_FLASH,
    "v4-pro": DEEPSEEK_V4_PRO,
    "pro": DEEPSEEK_V4_PRO,
}


def normalize_deepseek_model(model: str) -> str:
    """Map legacy or shorthand DeepSeek model names to canonical V4 ids."""
    normalized = model.strip().lower()
    if normalized in DEEPSEEK_MODEL_OPTIONS:
        return normalized
    if normalized in _LEGACY_DEEPSEEK_MODELS:
        return _LEGACY_DEEPSEEK_MODELS[normalized]
    if normalized in _DEEPSEEK_MODEL_ALIASES:
        return _DEEPSEEK_MODEL_ALIASES[normalized]
    return normalized


def resolve_deepseek_model_choice(choice: str) -> str:
    """Parse interactive or CLI input into a supported DeepSeek V4 model id."""
    normalized = normalize_deepseek_model(choice)
    if normalized in DEEPSEEK_MODEL_OPTIONS:
        return normalized
    if choice.strip() == "1":
        return DEEPSEEK_V4_FLASH
    if choice.strip() == "2":
        return DEEPSEEK_V4_PRO
    valid = ", ".join(DEEPSEEK_MODEL_OPTIONS)
    raise ConfigurationError(f"Unknown DeepSeek model '{choice}'. Choose one of: {valid}")


def format_deepseek_model_menu() -> str:
    lines = ["DeepSeek V4 models:"]
    for index, (model_id, label) in enumerate(DEEPSEEK_MODEL_OPTIONS.items(), start=1):
        lines.append(f"  {index}. {model_id} — {label}")
    return "\n".join(lines)


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
class UIConfig:
    assistant_color: str = "bright_cyan"
    user_color: str = "bright_white"
    thinking_color: str = "yellow"
    success_color: str = "green"
    error_color: str = "red"


def _load_ui_config(file_data: dict) -> UIConfig:
    ui_table = file_data.get("ui") or {}
    if not isinstance(ui_table, dict):
        ui_table = {}
    return UIConfig(
        assistant_color=str(ui_table.get("assistant_color", "bright_cyan")),
        user_color=str(ui_table.get("user_color", "bright_white")),
        thinking_color=str(ui_table.get("thinking_color", "yellow")),
        success_color=str(ui_table.get("success_color", "green")),
        error_color=str(ui_table.get("error_color", "red")),
    )


@dataclass
class Config:
    openai_api_key: str = ""
    deepseek_api_key: str = ""
    llm_provider: str = ""
    db_path: Path = field(default_factory=lambda: Path("~/.smith/memory.db").expanduser())
    openai_model: str = "gpt-4o-mini"
    deepseek_model: str = DEFAULT_DEEPSEEK_MODEL
    config_file_path: Path = field(default_factory=get_config_file_path)
    config_file_loaded: bool = False
    ui: UIConfig = field(default_factory=UIConfig)

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
            openai_api_key=os.environ.get("OPENAI_API_KEY", "").strip(),
            deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY", "").strip(),
            llm_provider=_get("SMITH_LLM_PROVIDER").lower(),
            db_path=db_path,
            openai_model=_get("OPENAI_MODEL", "gpt-4o-mini"),
            deepseek_model=normalize_deepseek_model(_get("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL)),
            config_file_path=config_path,
            config_file_loaded=config_file_loaded,
            ui=_load_ui_config(file_data),
        )

    def save(self) -> None:
        """Persist non-secret settings to config.toml. Never writes API keys."""
        path = self.config_file_path
        path.parent.mkdir(parents=True, exist_ok=True)

        home = Path.home()
        try:
            db_display = f"~/{self.db_path.relative_to(home)}"
        except ValueError:
            db_display = str(self.db_path)

        lines: list[str] = []
        if self.llm_provider:
            lines.append(f'smith_llm_provider = "{self.llm_provider}"')
        lines.append(f'db_path = "{db_display}"')
        lines.append(f'openai_model = "{self.openai_model}"')
        lines.append(f'deepseek_model = "{self.deepseek_model}"')
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.config_file_loaded = True


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


def get_active_model(config: Config) -> str | None:
    try:
        provider = resolve_provider(config)
    except ConfigurationError:
        return None
    if provider == "openai":
        return config.openai_model
    return normalize_deepseek_model(config.deepseek_model)


def needs_setup(config: Config) -> bool:
    try:
        resolve_provider(config)
        return False
    except ConfigurationError:
        return True
