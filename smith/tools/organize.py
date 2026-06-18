import logging
import shutil
from collections import Counter
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

CATEGORY_DIR_NAMES = set(CATEGORIES) | {"Misc"}


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
            return ToolResult(success=False, message=f"Not a directory: {directory}")

        if directory.name in CATEGORY_DIR_NAMES:
            return ToolResult(
                success=True,
                message=f"Skipping {directory} — already inside a category folder.",
                metadata={"files_moved": 0, "dry_run": dry_run, "categories": {}},
            )

        files = [p for p in directory.iterdir() if p.is_file() and not p.name.startswith(".")]

        if not files:
            return ToolResult(
                success=True,
                message=f"No files to organize in {directory}",
                metadata={"files_moved": 0, "dry_run": dry_run, "categories": {}},
            )

        moves: list[tuple[Path, Path]] = []
        category_counts: Counter[str] = Counter()
        for file_path in sorted(files):
            category = _categorize(file_path)
            dest_dir = directory / category
            dest = _unique_dest(dest_dir, file_path.name)
            moves.append((file_path, dest))
            category_counts[category] += 1

        summary_parts = [f"{cat}: {count}" for cat, count in sorted(category_counts.items())]
        lines = [
            f"Organize plan for {directory}:",
            f"Summary: {', '.join(summary_parts)}",
            "",
        ]
        for src, dest in moves:
            lines.append(f"  {src.name} -> {dest.relative_to(directory)}")

        metadata = {
            "files_moved": len(moves) if not dry_run else 0,
            "dry_run": dry_run,
            "categories": dict(category_counts),
        }

        if dry_run:
            lines.insert(1, "(dry-run — no files moved)")
            return ToolResult(success=True, message="\n".join(lines), metadata=metadata)

        for src, dest in moves:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))
            logger.info("Moved %s -> %s", src, dest)

        lines.append("")
        lines.append(f"Moved {len(moves)} file(s).")
        metadata["files_moved"] = len(moves)
        return ToolResult(success=True, message="\n".join(lines), metadata=metadata)
