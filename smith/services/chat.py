import logging
import shlex
from pathlib import Path

import typer

from smith.cli.banner import render_slash_commands_table, render_startup_banner
from smith.core.config import Config, get_active_model
from smith.core.formatting import format_result_footer
from smith.llm.base import LLMProvider
from smith.memory.service import MemoryService
from smith.models.project_context import ProjectContext
from smith.services.git_intelligence import GitIntelligenceService
from smith.services.project_context import ProjectContextService, format_context_text
from smith.services.slash_commands import dispatch_slash_command
from smith.services.tool_runner import (
    run_analyze,
    run_duplicates,
    run_organize,
    run_refresh_context,
    run_summarize,
    run_workstation_health,
)
from smith.tools.base import ToolResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Smith, a benevolent personal AI operator.
You help with software development, file organization, document analysis, and productivity.
Be concise and practical."""


def _parse_flag(args: list[str], flag: str) -> tuple[list[str], bool]:
    remaining = args[:]
    found = False
    while flag in remaining:
        remaining.remove(flag)
        found = True
    return remaining, found


def _parse_option(args: list[str], flag: str) -> tuple[list[str], str | None]:
    remaining = []
    value = None
    i = 0
    while i < len(args):
        if args[i] == flag and i + 1 < len(args):
            value = args[i + 1]
            i += 2
        else:
            remaining.append(args[i])
            i += 1
    return remaining, value


class ChatService:
    def __init__(
        self,
        llm: LLMProvider,
        memory: MemoryService,
        config: Config,
        *,
        workspace: Path | None = None,
    ) -> None:
        self._llm = llm
        self._memory = memory
        self._config = config
        self._provider = llm.name
        self._model = get_active_model(config) or "—"
        self._workspace = (workspace or Path.cwd()).resolve()
        self._context_service = ProjectContextService()
        self._project_context = self._context_service.load(self._workspace)

    def _system_prompt(self) -> str:
        parts = [SYSTEM_PROMPT]
        if self._project_context:
            parts.append("")
            parts.append(self._project_context.to_prompt_block())
        return "\n".join(parts)

    def run(self) -> None:
        session_id = self._memory.start_session()
        render_startup_banner(self._config, self._memory)
        render_slash_commands_table()
        if self._project_context:
            typer.echo(
                f"Loaded project context for {self._project_context.project_name} "
                f"from .smith/project_context.json"
            )

        while True:
            try:
                user_input = typer.prompt("You").strip()
            except (EOFError, KeyboardInterrupt):
                typer.echo("\nGoodbye.")
                break

            if not user_input:
                continue

            if user_input.lower() in ("/exit", "/quit"):
                typer.echo("Goodbye.")
                break

            self._memory.add_message(session_id, "user", user_input)

            if user_input.startswith("/"):
                response = self._handle_slash_command(user_input)
            else:
                response = self._handle_chat(session_id, user_input)

            typer.echo(f"\nSmith: {response}\n")
            self._memory.add_message(session_id, "assistant", response)

    def _handle_chat(self, session_id: str, user_input: str) -> str:
        history = self._memory.get_recent_messages(session_id, limit=20)
        parts = [self._system_prompt(), ""]
        for role, content in history[:-1]:
            label = "User" if role == "user" else "Assistant"
            parts.append(f"{label}: {content}")
        parts.append(f"User: {user_input}")
        prompt = "\n".join(parts)
        body = self._llm.generate(prompt)
        footer = format_result_footer(
            "chat",
            0,
            provider=self._provider,
            model=self._model,
        )
        return f"{body}\n\n{footer}"

    def _handle_slash_command(self, user_input: str) -> str:
        try:
            tokens = shlex.split(user_input)
        except ValueError as exc:
            return f"Invalid command: {exc}"

        if not tokens:
            return "Empty command."

        return dispatch_slash_command(
            self,
            tokens[0].lower(),
            tokens[1:],
            provider=self._provider,
            model=self._model,
        )

    def _cmd_show_context(self) -> str:
        if not self._project_context:
            return (
                "No project context loaded. Run `smith context .` or `/refresh-context` "
                "from a project directory."
            )
        return format_context_text(self._project_context)

    def _cmd_refresh_context(self) -> str:
        result = run_refresh_context(self._workspace)
        if not result.success:
            return result.message
        self._project_context = ProjectContext.from_dict(result.metadata["context"])
        return result.message

    def _analyze_structure_only(self, args: list[str]) -> bool:
        _, flag = _parse_flag(args, "--structure-only")
        return flag

    def _cmd_duplicates(self, args: list[str]) -> ToolResult:
        min_size = 0
        remaining = args[:]
        if "--min-size" in remaining:
            idx = remaining.index("--min-size")
            if idx + 1 < len(remaining):
                try:
                    min_size = int(remaining[idx + 1])
                except ValueError:
                    return ToolResult(success=False, message="Invalid --min-size value")
                del remaining[idx : idx + 2]
            else:
                return ToolResult(success=False, message="Usage: /duplicates <path> [--min-size N]")
        if not remaining:
            return ToolResult(success=False, message="Usage: /duplicates <path> [--min-size N]")
        return run_duplicates(remaining[0], min_size=min_size)

    def _cmd_organize(self, args: list[str]) -> ToolResult:
        args, dry_run = _parse_flag(args, "--dry-run")
        if not args:
            return ToolResult(success=False, message="Usage: /organize [--dry-run] <path>")
        if not dry_run:
            if not typer.confirm(f"Organize files in {args[0]}?"):
                return ToolResult(success=True, message="Organize cancelled.")
        return run_organize(args[0], dry_run=dry_run)

    def _cmd_analyze(self, args: list[str]) -> ToolResult:
        args, structure_only = _parse_flag(args, "--structure-only")
        output = None
        args, out_val = _parse_option(args, "-o")
        if out_val:
            output = Path(out_val)
        args, out_val = _parse_option(args, "--output")
        if out_val:
            output = Path(out_val)
        if not args:
            return ToolResult(
                success=False,
                message="Usage: /analyze <path> [--structure-only] [-o report.md]",
            )
        return run_analyze(
            args[0],
            self._llm,
            output=output,
            structure_only=structure_only,
        )

    def _cmd_summarize(self, args: list[str]) -> ToolResult:
        args, study_notes = _parse_flag(args, "--study-notes")
        pages = None
        args, pages_val = _parse_option(args, "--pages")
        if pages_val:
            try:
                pages = int(pages_val)
            except ValueError:
                return ToolResult(success=False, message="Invalid --pages value")
        if not args:
            return ToolResult(
                success=False,
                message="Usage: /summarize <pdf> [--study-notes] [--pages N]",
            )
        return run_summarize(args[0], self._llm, study_notes=study_notes, pages=pages)

    def _cmd_health(self, args: list[str]) -> ToolResult:
        if not args:
            return run_workstation_health()
        return run_workstation_health(paths=[args[0]])

    def _git_service(self) -> GitIntelligenceService:
        return GitIntelligenceService(cwd=self._workspace)
