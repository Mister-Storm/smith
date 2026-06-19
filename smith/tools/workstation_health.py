import json
import logging

from smith.services.workstation_health import build_workstation_report, report_to_markdown
from smith.tools.base import Tool, ToolResult

logger = logging.getLogger(__name__)


class WorkstationHealthTool(Tool):
    name = "health"
    description = "Read-only workstation hygiene scan with safe recommendations"

    def execute(self, **kwargs) -> ToolResult:
        from pathlib import Path

        paths_arg = kwargs.get("paths")
        paths: list[Path] | None = None
        if paths_arg:
            paths = [Path(p) for p in paths_arg]

        as_json = bool(kwargs.get("as_json", False))
        report = build_workstation_report(
            paths,
            stale_days=int(kwargs.get("stale_days", 90)),
            min_size_mb=int(kwargs.get("min_size_mb", 50)),
            max_depth=int(kwargs.get("max_depth", 4)),
            max_files=int(kwargs.get("max_files", 5000)),
        )

        message = json.dumps(report.to_dict(), indent=2) if as_json else report_to_markdown(report)

        metadata = {
            "score": report.score,
            "score_breakdown": report.score_breakdown,
            "exit_code": report.exit_code,
            "scanned_paths": report.scanned_paths,
            "report": report.to_dict(),
        }

        logger.info(
            "Tool health score=%d paths=%s",
            report.score,
            report.scanned_paths,
        )
        return ToolResult(success=True, message=message, metadata=metadata)
