"""Ensure Smith-generated .smith/ artifacts are listed in .gitignore."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

SMITH_GITIGNORE_ENTRIES = (
    ".smith/*",
    "!.smith/.gitkeep",
)


def resolve_git_repo_root(path: Path) -> Path | None:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=path.expanduser().resolve(),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    root = result.stdout.strip()
    return Path(root).resolve() if root else None


def _gitignore_has_smith_entry(lines: list[str]) -> bool:
    has_smith_glob = False
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        normalized = stripped.rstrip("/")
        if normalized in (
            ".smith",
            ".smith/project_context.json",
            ".smith/workspace_context.json",
            ".smith/workstation_health.json",
        ):
            return True
        if stripped in (".smith/", ".smith"):
            return True
        if stripped == ".smith/*":
            has_smith_glob = True
    return has_smith_glob


def ensure_smith_gitignore_entry(root: Path) -> None:
    """Append .smith gitignore rules at the git repository root when missing."""
    repo_root = resolve_git_repo_root(root)
    if repo_root is None:
        return

    gitignore_path = repo_root / ".gitignore"
    if not gitignore_path.is_file():
        return

    try:
        original = gitignore_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not read %s: %s", gitignore_path, exc)
        return

    if _gitignore_has_smith_entry(original.splitlines()):
        return

    block = "\n".join(SMITH_GITIGNORE_ENTRIES) + "\n"
    if original and not original.endswith("\n"):
        new_content = original + "\n" + block
    else:
        new_content = original + block

    try:
        gitignore_path.write_text(new_content, encoding="utf-8")
        logger.info("Added Smith .smith gitignore entries to %s", gitignore_path)
    except OSError as exc:
        logger.warning("Could not update %s: %s", gitignore_path, exc)
