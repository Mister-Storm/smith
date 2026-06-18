import json
import logging
from pathlib import Path

from smith.llm.base import LLMProvider
from smith.tools.base import Tool, ToolResult
from smith.tools.project_context import (
    ProjectContext,
    build_analysis_json,
    compute_health_score,
    context_to_markdown,
    generate_architecture_observations,
    generate_project_context,
)

logger = logging.getLogger(__name__)


def _format_context_header(context: ProjectContext) -> str:
    return "\n".join(
        [
            "---",
            f"**Path:** {context.project_path}",
            f"**Language:** {context.language or 'Unknown'}",
            f"**Frameworks:** {', '.join(context.frameworks) or 'None'}",
            f"**Build System:** {context.build_system or 'Unknown'}",
            f"**Modules:** {', '.join(context.modules) or 'N/A'}",
            "---",
            "",
        ]
    )


class AnalyzeProjectTool(Tool):
    name = "analyze"
    description = "Analyze project structure and generate architecture summary"

    def __init__(self, llm: LLMProvider | None = None) -> None:
        self._llm = llm

    def execute(self, **kwargs) -> ToolResult:
        project_path = Path(kwargs["path"]).expanduser().resolve()
        structure_only = bool(kwargs.get("structure_only", False))
        as_json = bool(kwargs.get("as_json", False))

        if not project_path.is_dir():
            return ToolResult(success=False, message=f"Not a directory: {project_path}")

        context = generate_project_context(project_path)
        health_score, issues = compute_health_score(context)
        observations = generate_architecture_observations(context)

        tool_metadata = {
            "language": (context.language or "unknown").lower(),
            "frameworks": [f.lower().replace(" ", "-") for f in context.frameworks],
            "build_system": context.build_system,
            "modules": len(context.modules),
            "health_score": health_score,
            "issues": issues,
            "structure_only": structure_only,
        }

        if as_json:
            payload = build_analysis_json(context, health_score, issues)
            message = json.dumps(payload, indent=2)
            return ToolResult(success=True, message=message, metadata=tool_metadata)

        health_section = f"\n## Project Health\n\nScore: {health_score}/100\n"
        header = _format_context_header(context)

        if structure_only:
            body = context_to_markdown(context) + health_section + "\n" + observations
            message = body
            logger.info("Tool analyze path=%s structure_only=True", project_path)
            return ToolResult(success=True, message=message, metadata=tool_metadata)

        context_block = json.dumps(context.to_dict(), indent=2)
        prompt = f"""Analyze this software project and produce markdown with these exact sections:

# Project Analysis

## Stack & Framework

## Structure

## Architecture Summary

## Suggested Review Areas

Use this structured ProjectContext as the primary source of truth:

{context_block}

Health score: {health_score}/100
Known issues: {", ".join(issues) if issues else "none"}

Be concise and practical."""

        system = "You are a senior software architect. Output only markdown."
        if self._llm is None:
            return ToolResult(
                success=False,
                message=(
                    "LLM provider required for full analysis. "
                    "Use --structure-only for offline scan."
                ),
            )
        llm_summary = self._llm.generate(prompt, system=system)
        message = header + llm_summary + "\n\n" + observations + "\n" + health_section

        logger.info(
            "Tool analyze path=%s score=%d modules=%d",
            project_path,
            health_score,
            len(context.modules),
        )
        return ToolResult(success=True, message=message, metadata=tool_metadata)
