import dataclasses
import logging
import time
from pathlib import Path
from typing import Any

from smith.llm.base import LLMProvider
from smith.tools.analyze_project import AnalyzeProjectTool
from smith.tools.base import Tool, ToolResult
from smith.tools.duplicates import FindDuplicateFilesTool
from smith.tools.organize import OrganizeDownloadsTool
from smith.tools.project_context import ProjectContextTool
from smith.tools.summarize_pdf import SummarizePdfTool

logger = logging.getLogger(__name__)


def _run_tool(tool: Tool, **kwargs: Any) -> ToolResult:
    start = time.perf_counter()
    try:
        result = tool.execute(**kwargs)
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.exception("Tool %s failed", tool.name)
        return ToolResult(
            success=False,
            message=str(exc),
            execution_time_ms=elapsed_ms,
            metadata={"execution_time_ms": elapsed_ms},
        )

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    metadata = {**(result.metadata or {}), "execution_time_ms": elapsed_ms}
    return dataclasses.replace(result, execution_time_ms=elapsed_ms, metadata=metadata)


def run_analyze(
    path: str | Path,
    llm: LLMProvider | None,
    *,
    output: Path | None = None,
    structure_only: bool = False,
    as_json: bool = False,
) -> ToolResult:
    tool = AnalyzeProjectTool(None if structure_only or as_json else llm)
    result = _run_tool(
        tool,
        path=str(path),
        structure_only=structure_only,
        as_json=as_json,
    )
    if result.success and output:
        output = Path(output)
        output.write_text(result.message, encoding="utf-8")
        return dataclasses.replace(result, output_path=output)
    return result


def run_context(
    path: str | Path,
    *,
    save: bool = True,
) -> ToolResult:
    tool = ProjectContextTool()
    result = _run_tool(tool, path=str(path), save=save, refresh=False)
    return result


def run_refresh_context(path: str | Path) -> ToolResult:
    tool = ProjectContextTool()
    return _run_tool(tool, path=str(path), save=True, refresh=True)


def run_summarize(
    path: str | Path,
    llm: LLMProvider,
    *,
    study_notes: bool = False,
    pages: int | None = None,
) -> ToolResult:
    tool = SummarizePdfTool(llm)
    kwargs: dict[str, Any] = {"path": str(path), "study_notes": study_notes}
    if pages is not None:
        kwargs["pages"] = pages
    return _run_tool(tool, **kwargs)


def run_duplicates(path: str | Path, *, min_size: int = 0) -> ToolResult:
    tool = FindDuplicateFilesTool()
    return _run_tool(tool, path=str(path), min_size=min_size)


def run_organize(path: str | Path, *, dry_run: bool = False) -> ToolResult:
    tool = OrganizeDownloadsTool()
    return _run_tool(tool, path=str(path), dry_run=dry_run)
