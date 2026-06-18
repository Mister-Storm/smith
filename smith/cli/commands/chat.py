import typer

from smith.core.config import Config
from smith.llm.factory import get_llm_provider
from smith.memory.service import MemoryService
from smith.services.chat import ChatService
from smith.services.setup_wizard import ensure_provider_configured


def chat(ctx: typer.Context) -> None:
    """Start an interactive chat session with Smith.

    Examples:

        smith chat
    """
    config = ensure_provider_configured(Config.load())
    llm = get_llm_provider(config)
    memory = MemoryService(config.db_path)
    service = ChatService(llm, memory, config)
    service.run()
