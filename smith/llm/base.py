from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, *, system: str | None = None) -> str:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass
