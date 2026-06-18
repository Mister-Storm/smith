import json
import logging
from collections import Counter
from pathlib import Path

from smith.llm.base import LLMProvider
from smith.tools.base import Tool, ToolResult
from smith.tools.fs_utils import should_skip_path

logger = logging.getLogger(__name__)

KOTLIN_MARKERS = {"build.gradle.kts"}
JAVA_MARKERS = {"pom.xml", "build.gradle"}
SPRING_MARKERS = {"application.yml", "application.properties", "application.yaml"}


def _read_snippet(path: Path, patterns: list[str], limit: int = 5) -> list[str]:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    lines = []
    for line in content.splitlines():
        if any(p in line for p in patterns):
            lines.append(line.strip())
            if len(lines) >= limit:
                break
    return lines


def _scan_project(path: Path, max_depth: int = 3) -> dict:
    extensions: Counter[str] = Counter()
    top_level_dirs: list[str] = []
    config_files: list[str] = []
    tree_lines: list[str] = []
    modules: list[str] = []
    entry_points: list[str] = []
    dependency_snippets: list[str] = []
    has_kotlin = False
    has_java = False
    has_spring = False
    build_system = "unknown"

    for item in sorted(path.iterdir()):
        if item.name.startswith("."):
            continue
        if item.is_dir():
            top_level_dirs.append(item.name)
        elif item.is_file():
            if item.name in KOTLIN_MARKERS:
                has_kotlin = True
                build_system = "Gradle (Kotlin DSL)"
            if item.name in JAVA_MARKERS:
                has_java = True
                if item.name == "pom.xml":
                    build_system = "Maven"
                elif build_system == "unknown":
                    build_system = "Gradle"

    for file_path in path.rglob("*"):
        if should_skip_path(file_path, path):
            continue
        if not file_path.is_file():
            continue

        ext = file_path.suffix.lower() or "(no ext)"
        extensions[ext] += 1
        rel = str(file_path.relative_to(path))

        if file_path.name in SPRING_MARKERS and rel not in config_files:
            config_files.append(rel)
            has_spring = True
        if file_path.suffix == ".kt":
            has_kotlin = True
            if file_path.name.endswith("Application.kt"):
                entry_points.append(rel)
        if file_path.suffix == ".java":
            has_java = True
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
                if "@SpringBootApplication" in text:
                    entry_points.append(rel)
                    has_spring = True
            except OSError:
                pass

        if file_path.name in ("pom.xml", "build.gradle", "build.gradle.kts"):
            parent_name = file_path.parent.name
            if file_path.parent != path and parent_name not in modules:
                modules.append(parent_name)
            snippets = _read_snippet(
                file_path,
                ["spring-boot-starter", "implementation", "api(", "compile("],
            )
            dependency_snippets.extend(snippets[:3])
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            if "spring-boot-starter" in content or "@SpringBootApplication" in content:
                has_spring = True

    def _walk_tree(current: Path, prefix: str = "", depth: int = 0) -> None:
        if depth > max_depth:
            return
        try:
            entries = sorted(
                [e for e in current.iterdir() if not e.name.startswith(".")],
                key=lambda e: (not e.is_dir(), e.name.lower()),
            )
        except OSError:
            return
        for i, entry in enumerate(entries):
            if entry.is_dir() and entry.name in {
                "node_modules",
                "target",
                "build",
                ".gradle",
                "__pycache__",
                ".venv",
                "venv",
            }:
                continue
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            tree_lines.append(f"{prefix}{connector}{entry.name}")
            if entry.is_dir() and depth < max_depth:
                extension = "    " if is_last else "│   "
                _walk_tree(entry, prefix + extension, depth + 1)

    _walk_tree(path)

    languages = []
    if has_kotlin:
        languages.append("Kotlin")
    if has_java:
        languages.append("Java")

    framework = "spring-boot" if has_spring else None

    return {
        "path": str(path),
        "languages": languages,
        "framework": framework,
        "build_system": build_system,
        "top_level_dirs": top_level_dirs,
        "modules": modules,
        "entry_points": entry_points[:10],
        "dependency_snippets": dependency_snippets[:10],
        "file_counts": dict(extensions.most_common(15)),
        "config_files": config_files,
        "tree": "\n".join(tree_lines[:50]),
        "total_files": sum(extensions.values()),
    }


def _metadata_from_scan(metadata: dict, *, structure_only: bool) -> dict:
    languages = metadata.get("languages", [])
    language = languages[0].lower() if languages else "unknown"
    if len(languages) > 1:
        language = "+".join(lang.lower() for lang in languages)
    return {
        "language": language,
        "framework": metadata.get("framework"),
        "build_system": metadata.get("build_system", "unknown"),
        "modules": len(metadata.get("modules", [])),
        "total_files": metadata.get("total_files", 0),
        "structure_only": structure_only,
    }


def _format_metadata_md(metadata: dict) -> str:
    return "\n".join(
        [
            "---",
            f"**Path:** {metadata['path']}",
            f"**Languages:** {', '.join(metadata['languages']) or 'Unknown'}",
            f"**Build System:** {metadata['build_system']}",
            f"**Total Files:** {metadata['total_files']}",
            f"**Modules:** {', '.join(metadata['modules']) or 'N/A'}",
            f"**Top-level Dirs:** {', '.join(metadata['top_level_dirs'])}",
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

        if not project_path.is_dir():
            return ToolResult(success=False, message=f"Not a directory: {project_path}")

        metadata = _scan_project(project_path)
        tool_metadata = _metadata_from_scan(metadata, structure_only=structure_only)
        metadata_md = _format_metadata_md(metadata)

        if structure_only:
            structure_body = "\n".join(
                [
                    "# Project Structure",
                    "",
                    "## File Tree",
                    "",
                    "```",
                    metadata.get("tree") or "(empty)",
                    "```",
                    "",
                ]
            )
            if metadata.get("entry_points"):
                structure_body += "## Entry Points\n\n" + "\n".join(
                    f"- `{ep}`" for ep in metadata["entry_points"]
                )
                structure_body += "\n"
            message = metadata_md + structure_body
            logger.info("Tool analyze path=%s structure_only=True", project_path)
            return ToolResult(success=True, message=message, metadata=tool_metadata)

        prompt = f"""Analyze this software project and produce markdown with these exact sections:

# Project Analysis

## Stack & Framework

## Structure

## Architecture Summary

## Suggested Review Areas

Project metadata:
{json.dumps(metadata, indent=2)}

Be concise and practical. Focus on Kotlin, Java, and Spring Boot if detected."""

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
        message = metadata_md + llm_summary

        logger.info("Tool analyze path=%s files=%d", project_path, metadata["total_files"])
        return ToolResult(success=True, message=message, metadata=tool_metadata)
