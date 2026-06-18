import logging
import shlex
from collections.abc import Callable

import typer

from smith.core.config import Config
from smith.llm.base import LLMProvider
from smith.memory.service import MemoryService
from smith.tools.analyze_project import AnalyzeProjectTool
from smith.tools.base import ToolResult
from smith.tools.duplicates import FindDuplicateFilesTool
from smith.tools.organize import OrganizeDownloadsTool
from smith.tools.summarize_pdf import SummarizePdfTool

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Smith, a benevolent personal AI operator.
You help with software development, file organization, document analysis, and productivity.
Be concise and practical."""

SLASH_COMMANDS_HELP = """
Slash commands:
  /duplicates <path>           Find duplicate files
  /organize <path>               Organize files (will ask for confirmation)
  /organize --dry-run <path>     Preview organize plan
  /analyze <path>                Analyze a project
  /summarize <pdf>               Summarize a PDF
  /exit                          Quit
"""


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
        self._duplicates = FindDuplicateFilesTool()
        self._organize = OrganizeDownloadsTool()
        self._analyze = AnalyzeProjectTool(llm)
        self._summarize = SummarizePdfTool(llm)

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

        handlers: dict[str, Callable[[list[str]], ToolResult]] = {
            "/duplicates": self._cmd_duplicates,
            "/organize": self._cmd_organize,
            "/analyze": self._cmd_analyze,
            "/summarize": self._cmd_summarize,
        }

        handler = handlers.get(command)
        if not handler:
            return f"Unknown command: {command}. Type /exit to quit."

        result = handler(args)
        if not result.success:
            return result.output
        return result.output

    def _cmd_duplicates(self, args: list[str]) -> ToolResult:
        if not args:
            return ToolResult(success=False, output="Usage: /duplicates <path>")
        return self._duplicates.execute(path=args[0])

    def _cmd_organize(self, args: list[str]) -> ToolResult:
        dry_run = False
        path_args = args[:]
        if "--dry-run" in path_args:
            dry_run = True
            path_args.remove("--dry-run")
        if not path_args:
            return ToolResult(success=False, output="Usage: /organize [--dry-run] <path>")

        if not dry_run:
            if not typer.confirm(f"Organize files in {path_args[0]}?"):
                return ToolResult(success=True, output="Organize cancelled.")

        return self._organize.execute(path=path_args[0], dry_run=dry_run)

    def _cmd_analyze(self, args: list[str]) -> ToolResult:
        if not args:
            return ToolResult(success=False, output="Usage: /analyze <path>")
        return self._analyze.execute(path=args[0])

    def _cmd_summarize(self, args: list[str]) -> ToolResult:
        if not args:
            return ToolResult(success=False, output="Usage: /summarize <pdf>")
        return self._summarize.execute(path=args[0])
