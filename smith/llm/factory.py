from smith.core.config import Config, resolve_provider
from smith.llm.base import LLMProvider
from smith.llm.deepseek_provider import DeepSeekProvider
from smith.llm.openai_provider import OpenAIProvider


def get_llm_provider(config: Config) -> LLMProvider:
    provider = resolve_provider(config)
    if provider == "openai":
        return OpenAIProvider(config)
    return DeepSeekProvider(config)
