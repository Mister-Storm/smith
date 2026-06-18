import hashlib
import logging
from collections import defaultdict
from pathlib import Path

from smith.tools.base import Tool, ToolResult

logger = logging.getLogger(__name__)


def _hash_file(path: Path, chunk_size: int = 65536) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


class FindDuplicateFilesTool(Tool):
    name = "duplicates"
    description = "Find duplicate files by content hash"

    def execute(self, **kwargs) -> ToolResult:
        directory = Path(kwargs["path"]).expanduser().resolve()
        min_size = int(kwargs.get("min_size", 0))

        if not directory.is_dir():
            return ToolResult(success=False, output=f"Not a directory: {directory}")

        hashes: dict[str, list[Path]] = defaultdict(list)
        file_count = 0

        for path in directory.rglob("*"):
            if not path.is_file():
                continue
            if any(part.startswith(".") for part in path.relative_to(directory).parts):
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size < min_size:
                continue
            file_count += 1
            file_hash = _hash_file(path)
            hashes[file_hash].append(path)

        duplicate_groups = [paths for paths in hashes.values() if len(paths) > 1]
        if not duplicate_groups:
            return ToolResult(
                success=True,
                output=f"Scanned {file_count} files in {directory}\nNo duplicates found.",
            )

        lines = [f"Scanned {file_count} files in {directory}", ""]
        total_wasted = 0
        for i, group in enumerate(duplicate_groups, 1):
            size = group[0].stat().st_size
            wasted = size * (len(group) - 1)
            total_wasted += wasted
            lines.append(
                f"Group {i} ({len(group)} files, {size} bytes each, {wasted} bytes wasted):"
            )
            for p in sorted(group):
                lines.append(f"  {p}")
            lines.append("")

        lines.append(f"Total wasted space: {total_wasted} bytes")
        logger.info("Tool duplicates scanned=%d groups=%d", file_count, len(duplicate_groups))
        return ToolResult(success=True, output="\n".join(lines))
