"""Lightweight terminal phase indicators for grounded assistant."""

from __future__ import annotations

from smith.cli.console import get_console
from smith.core.config import UIConfig


class ThinkingRenderer:
    def __init__(
        self,
        *,
        enabled: bool = True,
        ui: UIConfig | None = None,
    ) -> None:
        self._enabled = enabled
        self._phases: list[str] = []
        self._ui = ui or UIConfig()

    def phase(self, label: str) -> None:
        self._phases.append(label)
        if not self._enabled:
            return
        console = get_console()
        thinking = self._ui.thinking_color
        markup = f"[dim {thinking}]{label}[/dim {thinking}]"
        console.print(markup if console.is_terminal else label)

    def complete(self, label: str, detail: str) -> None:
        if not self._enabled:
            return
        console = get_console()
        success = self._ui.success_color
        text = f"✓ {detail}"
        markup = f"[{success}]{text}[/{success}]"
        console.print(markup if console.is_terminal else text)

    def warning(self, message: str) -> None:
        if not self._enabled:
            return
        console = get_console()
        thinking = self._ui.thinking_color
        markup = f"[{thinking}]⚠ {message}[/{thinking}]"
        console.print(markup if console.is_terminal else f"⚠ {message}")

    def error(self, message: str) -> None:
        if not self._enabled:
            return
        console = get_console()
        err = self._ui.error_color
        markup = f"[{err}]✗ {message}[/{err}]"
        console.print(markup if console.is_terminal else f"✗ {message}")

    @property
    def phases(self) -> list[str]:
        return list(self._phases)
