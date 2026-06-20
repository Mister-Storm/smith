from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from smith.core.exceptions import GitNotRepositoryError
from smith.core.formatting import format_result_footer
from smith.services.git_intelligence import (
    GitIntelligenceService,
    format_commit_suggestions,
    format_git_changes,
    format_git_health,
    format_git_summary,
    format_release_notes,
)
from smith.tools.base import ToolResult

if TYPE_CHECKING:
    from smith.services.chat import ChatService


class SlashResponseMode(StrEnum):
    TEXT = "text"
    TOOL = "tool"
    TOOL_WITH_LLM = "tool_with_llm"


@dataclass(frozen=True, slots=True)
class SlashCommandSpec:
    name: str
    handler: Callable[[ChatService, list[str]], str | ToolResult]
    mode: SlashResponseMode = SlashResponseMode.TOOL
    extra_format: Callable[[ChatService, list[str]], dict[str, Any]] | None = None


def _format_tool_response(
    result: ToolResult,
    tool_name: str,
    *,
    provider: str | None = None,
    model: str | None = None,
) -> str:
    parts = [result.message]
    if result.output_path:
        parts.append(f"Report written to {result.output_path}")
    if result.success:
        parts.append(
            format_result_footer(
                tool_name,
                max(result.execution_time_ms, 0),
                provider=provider,
                model=model,
            )
        )
    return "\n".join(parts)


def _git_tool_result(
    service: ChatService,
    fn: Callable[[GitIntelligenceService], str],
) -> ToolResult:
    try:
        return ToolResult(success=True, message=fn(service._git_service()))
    except GitNotRepositoryError as exc:
        return ToolResult(success=False, message=str(exc))


def _handle_context(service: ChatService, args: list[str]) -> str:
    return service._cmd_show_context()


def _handle_refresh_context(service: ChatService, args: list[str]) -> str:
    return service._cmd_refresh_context()


def _handle_duplicates(service: ChatService, args: list[str]) -> ToolResult:
    return service._cmd_duplicates(args)


def _handle_organize(service: ChatService, args: list[str]) -> ToolResult:
    return service._cmd_organize(args)


def _handle_analyze(service: ChatService, args: list[str]) -> ToolResult:
    return service._cmd_analyze(args)


def _analyze_format_kwargs(service: ChatService, args: list[str]) -> dict[str, Any]:
    if service._analyze_structure_only(args):
        return {}
    return {"provider": service._provider, "model": service._model}


def _handle_summarize(service: ChatService, args: list[str]) -> ToolResult:
    return service._cmd_summarize(args)


def _handle_health(service: ChatService, args: list[str]) -> ToolResult:
    return service._cmd_health(args)


def _handle_git_summary(service: ChatService, args: list[str]) -> ToolResult:
    def build(git: GitIntelligenceService) -> str:
        status = git.get_repository_status()
        suggestions = git.suggest_commit_messages()
        areas = git.summarize_changes().areas
        return format_git_summary(status, suggestions, areas=areas)

    return _git_tool_result(service, build)


def _handle_git_changes(service: ChatService, args: list[str]) -> ToolResult:
    return _git_tool_result(service, lambda git: format_git_changes(git.summarize_changes()))


def _handle_commit_message(service: ChatService, args: list[str]) -> ToolResult:
    return _git_tool_result(
        service,
        lambda git: format_commit_suggestions(git.suggest_commit_messages()),
    )


def _handle_release_notes(service: ChatService, args: list[str]) -> ToolResult:
    return _git_tool_result(
        service,
        lambda git: format_release_notes(git.generate_release_notes()),
    )


def _handle_git_health(service: ChatService, args: list[str]) -> ToolResult:
    return _git_tool_result(service, lambda git: format_git_health(git.get_git_health()))


def build_slash_command_registry() -> dict[str, SlashCommandSpec]:
    return {
        "/context": SlashCommandSpec("/context", _handle_context, SlashResponseMode.TEXT),
        "/refresh-context": SlashCommandSpec(
            "/refresh-context", _handle_refresh_context, SlashResponseMode.TEXT
        ),
        "/duplicates": SlashCommandSpec("/duplicates", _handle_duplicates),
        "/organize": SlashCommandSpec("/organize", _handle_organize),
        "/analyze": SlashCommandSpec(
            "/analyze",
            _handle_analyze,
            SlashResponseMode.TOOL_WITH_LLM,
            extra_format=_analyze_format_kwargs,
        ),
        "/summarize": SlashCommandSpec(
            "/summarize", _handle_summarize, SlashResponseMode.TOOL_WITH_LLM
        ),
        "/health": SlashCommandSpec("/health", _handle_health),
        "/git-summary": SlashCommandSpec("/git-summary", _handle_git_summary),
        "/git-changes": SlashCommandSpec("/git-changes", _handle_git_changes),
        "/commit-message": SlashCommandSpec("/commit-message", _handle_commit_message),
        "/release-notes": SlashCommandSpec("/release-notes", _handle_release_notes),
        "/git-health": SlashCommandSpec("/git-health", _handle_git_health),
    }


SLASH_COMMANDS = build_slash_command_registry()


def dispatch_slash_command(
    service: ChatService,
    command: str,
    args: list[str],
    *,
    provider: str,
    model: str,
) -> str:
    spec = SLASH_COMMANDS.get(command)
    if spec is None:
        return f"Unknown command: {command}. Type /exit to quit."

    result = spec.handler(service, args)
    if spec.mode == SlashResponseMode.TEXT:
        assert isinstance(result, str)
        return result

    assert isinstance(result, ToolResult)
    tool_name = spec.name.lstrip("/")
    format_kwargs: dict[str, Any] = {}
    if spec.extra_format is not None:
        format_kwargs = spec.extra_format(service, args)
    elif spec.mode == SlashResponseMode.TOOL_WITH_LLM:
        format_kwargs = {"provider": provider, "model": model}
    return _format_tool_response(result, tool_name, **format_kwargs)
