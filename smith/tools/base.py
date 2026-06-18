from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ToolResult:
    success: bool
    message: str
    output_path: Path | None = None
    metadata: dict[str, Any] | None = None
    execution_time_ms: int = 0


class Tool(ABC):
    name: str
    description: str

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        pass
