import typer

from smith.core.config import Config
from smith.core.exceptions import ConfigurationError
from smith.llm.factory import get_llm_provider
from smith.memory.service import MemoryService
from smith.services.chat import ChatService


def chat(ctx: typer.Context) -> None:
    """Start an interactive chat session with Smith."""
    config = Config.load()
    try:
        llm = get_llm_provider(config)
    except ConfigurationError as exc:
        typer.echo(f"Configuration error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    memory = MemoryService(config.db_path)
    service = ChatService(llm, memory, config)
    service.run()
