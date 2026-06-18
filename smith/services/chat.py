import logging
import shlex

import typer

from smith.core.config import Config
from smith.core.formatting import format_completion_line
from smith.llm.base import LLMProvider
from smith.memory.service import MemoryService
from smith.services.tool_runner import run_analyze, run_duplicates, run_organize, run_summarize
from smith.tools.base import ToolResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Smith, a benevolent personal AI operator.
You help with software development, file organization, document analysis, and productivity.
Be concise and practical."""

SLASH_COMMANDS_HELP = """
Slash commands:
  /duplicates <path> [--min-size N]     Find duplicate files
  /organize <path> [--dry-run]           Organize files (asks for confirmation)
  /analyze <path> [--structure-only]     Analyze a project
  /analyze <path> -o report.md           Analyze and save report
  /summarize <pdf> [--study-notes]       Summarize a PDF
  /summarize <pdf> --pages N             Summarize first N pages
  /exit                                  Quit
"""


def _format_tool_response(result: ToolResult, tool_name: str) -> str:
    parts = [result.message]
    if result.output_path:
        parts.append(f"Report written to {result.output_path}")
    if result.success:
        parts.append(format_completion_line(tool_name, max(result.execution_time_ms, 0)))
    return "\n".join(parts)


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
    ) -> None:
        self._llm = llm
        self._memory = memory
        self._config = config

    def run(self) -> None:
        session_id = self._memory.start_session()
        typer.echo(f"Smith chat (provider: {self._llm.name}, session: {session_id[:8]}...)")
        typer.echo("Type a message or use a slash command. /exit to quit.")
        typer.echo(SLASH_COMMANDS_HELP)

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
        parts = [SYSTEM_PROMPT, ""]
        for role, content in history[:-1]:
            label = "User" if role == "user" else "Assistant"
            parts.append(f"{label}: {content}")
        parts.append(f"User: {user_input}")
        prompt = "\n".join(parts)
        return self._llm.generate(prompt)

    def _handle_slash_command(self, user_input: str) -> str:
        try:
            tokens = shlex.split(user_input)
        except ValueError as exc:
            return f"Invalid command: {exc}"

        if not tokens:
            return "Empty command."

        command = tokens[0].lower()
        args = tokens[1:]

        if command == "/duplicates":
            return _format_tool_response(self._cmd_duplicates(args), "duplicates")
        if command == "/organize":
            return _format_tool_response(self._cmd_organize(args), "organize")
        if command == "/analyze":
            return _format_tool_response(self._cmd_analyze(args), "analyze")
        if command == "/summarize":
            return _format_tool_response(self._cmd_summarize(args), "summarize")

        return f"Unknown command: {command}. Type /exit to quit."

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
            from pathlib import Path

            output = Path(out_val)
        args, out_val = _parse_option(args, "--output")
        if out_val:
            from pathlib import Path

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
