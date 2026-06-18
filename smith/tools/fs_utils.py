from pathlib import Path

SKIP_DIR_NAMES = {
    ".git",
    "node_modules",
    "target",
    "build",
    ".gradle",
    "__pycache__",
    ".venv",
    "venv",
}


def should_skip_path(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return True
    return any(part.startswith(".") or part in SKIP_DIR_NAMES for part in rel.parts)


def format_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    if n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{n / (1024 * 1024 * 1024):.2f} GB"
