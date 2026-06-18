import logging
import shutil
from pathlib import Path

from smith.tools.base import Tool, ToolResult

logger = logging.getLogger(__name__)

CATEGORIES: dict[str, set[str]] = {
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".md", ".xls", ".xlsx"},
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"},
    "Videos": {".mp4", ".mkv", ".avi", ".mov", ".webm"},
    "Archives": {".zip", ".tar", ".gz", ".rar", ".7z"},
    "Code": {
        ".py",
        ".java",
        ".kt",
        ".js",
        ".ts",
        ".go",
        ".rs",
        ".xml",
        ".json",
        ".yaml",
        ".yml",
    },
}


def _categorize(path: Path) -> str:
    ext = path.suffix.lower()
    for category, extensions in CATEGORIES.items():
        if ext in extensions:
            return category
    return "Misc"


def _unique_dest(dest_dir: Path, filename: str) -> Path:
    dest = dest_dir / filename
    if not dest.exists():
        return dest
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    counter = 1
    while True:
        candidate = dest_dir / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


class OrganizeDownloadsTool(Tool):
    name = "organize"
    description = "Organize files into category folders"

    def execute(self, **kwargs) -> ToolResult:
        directory = Path(kwargs["path"]).expanduser().resolve()
        dry_run = bool(kwargs.get("dry_run", False))

        if not directory.is_dir():
            return ToolResult(success=False, output=f"Not a directory: {directory}")

        files = [p for p in directory.iterdir() if p.is_file() and not p.name.startswith(".")]

        if not files:
            return ToolResult(success=True, output=f"No files to organize in {directory}")

        moves: list[tuple[Path, Path]] = []
        for file_path in sorted(files):
            category = _categorize(file_path)
            dest_dir = directory / category
            dest = _unique_dest(dest_dir, file_path.name)
            moves.append((file_path, dest))

        lines = [f"Organize plan for {directory}:", ""]
        for src, dest in moves:
            lines.append(f"  {src.name} -> {dest.relative_to(directory)}")

        if dry_run:
            lines.insert(1, "(dry-run — no files moved)")
            return ToolResult(success=True, output="\n".join(lines))

        for src, dest in moves:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))
            logger.info("Moved %s -> %s", src, dest)

        lines.append("")
        lines.append(f"Moved {len(moves)} file(s).")
        return ToolResult(success=True, output="\n".join(lines))
