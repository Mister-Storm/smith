import hashlib
import logging
from collections import defaultdict
from pathlib import Path

from smith.tools.base import Tool, ToolResult
from smith.tools.fs_utils import format_bytes, should_skip_path

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
            return ToolResult(success=False, message=f"Not a directory: {directory}")

        hashes: dict[str, list[Path]] = defaultdict(list)
        file_count = 0

        for path in directory.rglob("*"):
            if not path.is_file() or should_skip_path(path, directory):
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
        duplicate_groups.sort(
            key=lambda group: group[0].stat().st_size * (len(group) - 1),
            reverse=True,
        )

        total_wasted = sum(group[0].stat().st_size * (len(group) - 1) for group in duplicate_groups)

        metadata = {
            "files_scanned": file_count,
            "duplicate_groups": len(duplicate_groups),
            "recoverable_bytes": total_wasted,
        }

        if not duplicate_groups:
            return ToolResult(
                success=True,
                message=f"Scanned {file_count} files in {directory}\nNo duplicates found.",
                metadata=metadata,
            )

        lines = [
            f"Scanned {file_count} files in {directory}",
            f"Found {len(duplicate_groups)} groups, {format_bytes(total_wasted)} recoverable",
            "",
        ]
        for i, group in enumerate(duplicate_groups, 1):
            size = group[0].stat().st_size
            wasted = size * (len(group) - 1)
            lines.append(
                f"Group {i} ({len(group)} files, {format_bytes(size)} each, "
                f"{format_bytes(wasted)} wasted):"
            )
            for p in sorted(group):
                lines.append(f"  {p}")
            lines.append("")

        lines.append(f"Total wasted space: {format_bytes(total_wasted)}")
        logger.info("Tool duplicates scanned=%d groups=%d", file_count, len(duplicate_groups))
        return ToolResult(success=True, message="\n".join(lines), metadata=metadata)
