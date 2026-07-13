"""Integration with Hermes Agent — delegate tasks to the Hermes CLI."""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path

from smith.tools.base import ToolResult

logger = logging.getLogger(__name__)

_HERMES_CMD = "hermes"


def run_hermes_task(task: str, *, workdir: str | Path | None = None) -> ToolResult:
    """Delegate a task to Hermes Agent via CLI.

    Args:
        task: Natural language task description for Hermes.
        workdir: Working directory to run Hermes from.

    Returns:
        ToolResult with Hermes output.
    """
    cwd = Path(workdir).resolve() if workdir else Path.cwd()

    if not _is_hermes_installed():
        return ToolResult(
            success=False,
            message="Hermes CLI not found. Install with: pipx install hermes-agent",
        )

    start = time.perf_counter()
    try:
        result = subprocess.run(
            [_HERMES_CMD, "--no-confirm", task],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(cwd),
        )
        elapsed = time.perf_counter() - start
        output = result.stdout.strip() or result.stderr.strip()

        if result.returncode == 0:
            logger.info("Hermes task completed in %.1fs: %s", elapsed, task[:80])
            return ToolResult(
                success=True,
                message=output or "Hermes task completed successfully.",
                execution_time_ms=int(elapsed * 1000),
            )
        logger.warning(
            "Hermes task failed (exit=%d, %.1fs): %s",
            result.returncode,
            elapsed,
            output[:200],
        )
        return ToolResult(
            success=False,
            message=f"Hermes returned exit code {result.returncode}:\n{output}",
            execution_time_ms=int(elapsed * 1000),
        )
    except subprocess.TimeoutExpired:
        logger.warning("Hermes task timed out after 120s: %s", task[:80])
        return ToolResult(success=False, message="Hermes task timed out after 120 seconds.")
    except FileNotFoundError:
        return ToolResult(
            success=False,
            message="Hermes CLI not found. Install with: pipx install hermes-agent",
        )
    except OSError as exc:
        return ToolResult(success=False, message=f"Hermes execution error: {exc}")


def _is_hermes_installed() -> bool:
    try:
        result = subprocess.run(
            [_HERMES_CMD, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, OSError):
        return False
