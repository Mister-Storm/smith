import json
import logging
from collections import Counter
from pathlib import Path

from smith.llm.base import LLMProvider
from smith.tools.base import Tool, ToolResult

logger = logging.getLogger(__name__)

KOTLIN_MARKERS = {"build.gradle.kts"}
JAVA_MARKERS = {"pom.xml", "build.gradle"}
SPRING_MARKERS = {"application.yml", "application.properties", "application.yaml"}


def _scan_project(path: Path, max_depth: int = 3) -> dict:
    extensions: Counter[str] = Counter()
    top_level_dirs: list[str] = []
    config_files: list[str] = []
    tree_lines: list[str] = []
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
        if any(part.startswith(".") for part in file_path.relative_to(path).parts):
            continue
        if file_path.is_file():
            ext = file_path.suffix.lower() or "(no ext)"
            extensions[ext] += 1
            rel = file_path.relative_to(path)
            if file_path.name in SPRING_MARKERS and str(rel) not in config_files:
                config_files.append(str(rel))
                has_spring = True
            if file_path.suffix == ".kt":
                has_kotlin = True
            if file_path.suffix == ".java":
                has_java = True
            if file_path.name in ("pom.xml", "build.gradle", "build.gradle.kts"):
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                if "spring-boot-starter" in content or "@SpringBootApplication" in content:
                    has_spring = True

    def _walk_tree(current: Path, prefix: str = "", depth: int = 0) -> None:
        if depth > max_depth:
            return
        entries = sorted(
            [e for e in current.iterdir() if not e.name.startswith(".")],
            key=lambda e: (not e.is_dir(), e.name.lower()),
        )
        for i, entry in enumerate(entries):
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
    if has_spring:
        languages.append("Spring Boot")

    return {
        "path": str(path),
        "languages": languages,
        "build_system": build_system,
        "top_level_dirs": top_level_dirs,
        "file_counts": dict(extensions.most_common(15)),
        "config_files": config_files,
        "tree": "\n".join(tree_lines[:50]),
        "total_files": sum(extensions.values()),
    }


class AnalyzeProjectTool(Tool):
    name = "analyze"
    description = "Analyze project structure and generate architecture summary"

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    def execute(self, **kwargs) -> ToolResult:
        project_path = Path(kwargs["path"]).expanduser().resolve()

        if not project_path.is_dir():
            return ToolResult(success=False, output=f"Not a directory: {project_path}")

        metadata = _scan_project(project_path)
        metadata_md = "\n".join(
            [
                "---",
                f"**Path:** {metadata['path']}",
                f"**Languages:** {', '.join(metadata['languages']) or 'Unknown'}",
                f"**Build System:** {metadata['build_system']}",
                f"**Total Files:** {metadata['total_files']}",
                f"**Top-level Dirs:** {', '.join(metadata['top_level_dirs'])}",
                "---",
                "",
            ]
        )

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
        llm_summary = self._llm.generate(prompt, system=system)
        output = metadata_md + llm_summary

        logger.info("Tool analyze path=%s files=%d", project_path, metadata["total_files"])
        return ToolResult(success=True, output=output)
