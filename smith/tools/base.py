from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ToolResult:
    success: bool
    output: str


class Tool(ABC):
    name: str
    description: str

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        pass
