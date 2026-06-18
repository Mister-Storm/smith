import logging
import time

from openai import OpenAI

from smith.core.config import Config
from smith.llm.base import LLMProvider

logger = logging.getLogger(__name__)

DEEPSEEK_BASE_URL = "https://api.deepseek.com"


class DeepSeekProvider(LLMProvider):
    def __init__(self, config: Config, client: OpenAI | None = None) -> None:
        self._config = config
        self._client = client or OpenAI(
            api_key=config.deepseek_api_key,
            base_url=DEEPSEEK_BASE_URL,
        )

    @property
    def name(self) -> str:
        return "DeepSeek"

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        start = time.perf_counter()
        response = self._client.chat.completions.create(
            model=self._config.deepseek_model,
            messages=messages,
        )
        elapsed = time.perf_counter() - start
        content = response.choices[0].message.content or ""
        logger.info(
            "LLM call provider=%s model=%s prompt_len=%d response_len=%d duration_ms=%.0f",
            self.name,
            self._config.deepseek_model,
            len(prompt),
            len(content),
            elapsed * 1000,
        )
        return content
