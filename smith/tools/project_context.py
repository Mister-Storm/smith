import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

from smith.services.context_detection import (
    BUILD_DISPLAY,
    CI_DISPLAY,
    DATABASE_DISPLAY,
    INFRA_DISPLAY,
    LANGUAGE_DISPLAY,
    detect_project_context,
)
from smith.tools.base import Tool, ToolResult
from smith.tools.fs_utils import should_skip_path

logger = logging.getLogger(__name__)

LAYER_NAMES = {
    "api",
    "service",
    "services",
    "repository",
    "repositories",
    "domain",
    "persistence",
    "controller",
    "controllers",
    "model",
    "models",
    "infra",
    "infrastructure",
    "application",
    "core",
    "shared",
    "common",
}


@dataclass(slots=True)
class AnalysisProjectContext:
    language: str | None
    frameworks: list[str]
    build_system: str | None
    databases: list[str]
    containers: list[str]
    ci_cd: list[str]
    modules: list[str]
    entry_points: list[str]
    architecture_layers: list[str]
    detected_patterns: list[str]
    project_path: str = ""
    has_tests: bool = False
    has_build_file: bool = False
    large_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AnalysisProjectContext":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _slug_to_display(slug: str | None, mapping: dict[str, str]) -> str | None:
    if not slug:
        return None
    return mapping.get(slug, slug.replace("-", " ").title())


def _detect_entry_points(path: Path) -> list[str]:
    entry_points: list[str] = []
    for file_path in path.rglob("*"):
        if not file_path.is_file() or should_skip_path(file_path, path):
            continue
        rel = str(file_path.relative_to(path))
        if file_path.name.endswith("Application.kt") or file_path.name.endswith("Application.java"):
            entry_points.append(rel)
            continue
        if file_path.suffix in (".java", ".kt"):
            content = _read_text(file_path)
            if "@SpringBootApplication" in content and rel not in entry_points:
                entry_points.append(rel)
        if file_path.name in ("main.py", "app.py", "__main__.py"):
            entry_points.append(rel)
    return entry_points[:10]


def _detect_layers(path: Path) -> list[str]:
    layers: set[str] = set()
    for item in path.iterdir():
        if item.is_dir() and item.name.lower() in LAYER_NAMES:
            layers.add(item.name.lower())
    for file_path in path.rglob("*"):
        if not file_path.is_dir() or should_skip_path(file_path, path):
            continue
        name = file_path.name.lower()
        if name in LAYER_NAMES:
            rel_parts = file_path.relative_to(path).parts
            if len(rel_parts) <= 3:
                layers.add(name)
    return sorted(layers)


def _detect_patterns(context: AnalysisProjectContext) -> list[str]:
    patterns: list[str] = []
    layers = set(context.architecture_layers)
    if {"api", "service", "repository"}.issubset(layers) or {
        "controller",
        "service",
        "repository",
    }.issubset(layers):
        patterns.append("Layered Architecture")
    if {"domain", "persistence"}.issubset(layers) or {"domain", "api"}.issubset(layers):
        patterns.append("Domain-Driven Design")
    if len(context.modules) >= 2:
        patterns.append("Multi-Module Project")
    if "Spring Boot" in context.frameworks:
        patterns.append("Spring Boot Application")
    if context.containers:
        patterns.append("Containerized Deployment")
    if context.ci_cd:
        patterns.append("Automated CI/CD")
    return patterns


def _detect_tests(path: Path) -> bool:
    test_dirs = {"test", "tests", "src/test", "src/test/java", "src/test/kotlin"}
    for file_path in path.rglob("*"):
        if not file_path.is_file() or should_skip_path(file_path, path):
            continue
        rel = file_path.relative_to(path)
        if any(part in ("test", "tests") for part in rel.parts):
            return True
        if file_path.name.startswith("test_") and file_path.suffix == ".py":
            return True
        if "Test" in file_path.name and file_path.suffix in (".java", ".kt"):
            return True
    for td in test_dirs:
        if (path / td).exists():
            return True
    return False


def _detect_large_files(path: Path, line_threshold: int = 400) -> list[str]:
    large: list[str] = []
    for file_path in path.rglob("*"):
        if not file_path.is_file() or should_skip_path(file_path, path):
            continue
        if file_path.suffix not in (".java", ".kt", ".py"):
            continue
        try:
            line_count = sum(1 for _ in file_path.open(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
        if line_count >= line_threshold:
            large.append(str(file_path.relative_to(path)))
    return large[:5]


def generate_project_context(project_path: Path) -> AnalysisProjectContext:
    path = project_path.expanduser().resolve()
    detected, _trace = detect_project_context(path)

    language = _slug_to_display(detected.language, LANGUAGE_DISPLAY)
    build_system = _slug_to_display(detected.build_system, BUILD_DISPLAY)
    has_build = build_system is not None

    context = AnalysisProjectContext(
        language=language,
        frameworks=detected.frameworks,
        build_system=build_system,
        databases=[DATABASE_DISPLAY.get(d, d) for d in detected.databases],
        containers=[INFRA_DISPLAY.get(i, i) for i in detected.infrastructure],
        ci_cd=[CI_DISPLAY.get(c, c) for c in detected.ci_cd],
        modules=detected.modules,
        entry_points=_detect_entry_points(path),
        architecture_layers=_detect_layers(path),
        detected_patterns=[],
        project_path=str(path),
        has_tests=_detect_tests(path),
        has_build_file=has_build,
        large_files=_detect_large_files(path),
    )
    context.detected_patterns = _detect_patterns(context)
    return context


def compute_health_score(context: AnalysisProjectContext) -> tuple[int, list[str]]:
    score = 50
    issues: list[str] = []

    if context.has_tests:
        score += 15
    else:
        score -= 15
        issues.append("missing tests")

    if context.ci_cd:
        score += 10
    else:
        score -= 5
        issues.append("no CI/CD detected")

    if context.containers:
        score += 5

    if context.has_build_file:
        score += 10
    else:
        score -= 20
        issues.append("missing build files")

    if len(context.modules) >= 2:
        score += 10
    elif len(context.modules) == 0 and context.language in ("Kotlin", "Java"):
        score -= 5
        issues.append("single-module or unclear module structure")

    if context.entry_points:
        score += 5
    else:
        issues.append("no clear entry point detected")

    if context.large_files:
        score -= min(10, len(context.large_files) * 3)
        issues.append("large service classes detected")

    if context.architecture_layers:
        score += 5

    return max(0, min(100, score)), issues


def generate_architecture_observations(context: AnalysisProjectContext) -> str:
    lines = ["## Architecture Observations", ""]

    if "Layered Architecture" in context.detected_patterns:
        layers = ", ".join(context.architecture_layers) or "api, service, repository"
        lines.append(f"The project follows a layered architecture ({layers}).")
        lines.append("")
        lines.append("The separation between layers appears consistent with common conventions.")
    elif context.architecture_layers:
        lines.append(f"Architectural layers detected: {', '.join(context.architecture_layers)}.")
    else:
        lines.append("No explicit architectural layering was detected from directory structure.")

    lines.append("")
    if len(context.entry_points) == 1:
        lines.append(
            "The project contains a single entry point and likely centralized configuration."
        )
    elif len(context.entry_points) > 1:
        lines.append(
            f"Multiple entry points detected ({len(context.entry_points)}), "
            "which may indicate several deployable units."
        )
    else:
        lines.append("No standard application entry point was identified.")

    if context.modules:
        lines.append("")
        lines.append(f"Module structure includes: {', '.join(context.modules)}.")

    if context.containers and context.ci_cd:
        lines.append("")
        lines.append(
            "Containerization and CI/CD tooling suggest a production-ready delivery pipeline."
        )

    return "\n".join(lines)


def context_to_markdown(context: AnalysisProjectContext) -> str:
    def section(title: str, items: list[str] | None, single: str | None = None) -> str:
        if single:
            body = single
        elif items:
            body = "\n".join(f"- {i}" for i in items)
        else:
            body = "- None detected"
        return f"## {title}\n{body}\n"

    parts = [
        "# Project Context",
        "",
        section("Languages", None, f"- {context.language}" if context.language else "- Unknown"),
        section("Frameworks", context.frameworks),
        section(
            "Build System",
            None,
            f"- {context.build_system}" if context.build_system else "- Unknown",
        ),
        section("Databases", context.databases),
        section("Containers", context.containers),
        section("CI/CD", context.ci_cd),
        section("Modules", context.modules),
        section(
            "Entry Points",
            [Path(ep).name for ep in context.entry_points] or context.entry_points,
        ),
        section("Architecture Layers", context.architecture_layers),
        section("Detected Patterns", context.detected_patterns),
    ]
    return "\n".join(parts)


def build_analysis_json(
    context: AnalysisProjectContext, health_score: int, issues: list[str]
) -> dict:
    return {
        "health_score": health_score,
        "language": (context.language or "unknown").lower(),
        "frameworks": [f.lower().replace(" ", "-") for f in context.frameworks],
        "modules": context.modules,
        "issues": issues,
        "build_system": context.build_system,
        "databases": context.databases,
        "ci_cd": context.ci_cd,
        "containers": context.containers,
        "architecture_layers": context.architecture_layers,
        "detected_patterns": context.detected_patterns,
    }


class ProjectContextTool(Tool):
    name = "context"
    description = "Generate structured project context snapshot"

    def execute(self, **kwargs) -> ToolResult:
        from smith.services.project_context import (
            ProjectContextService,
            format_context_text,
            render_detection_debug,
        )

        project_path = Path(kwargs["path"]).expanduser().resolve()
        save = bool(kwargs.get("save", True))
        refresh = bool(kwargs.get("refresh", False))
        debug = bool(kwargs.get("debug", False))

        if not project_path.is_dir():
            return ToolResult(success=False, message=f"Not a directory: {project_path}")

        service = ProjectContextService()
        trace = None
        try:
            if refresh:
                context, trace = service.refresh(project_path, debug=debug)
            else:
                context, trace = service.build(project_path, debug=debug)
                if save:
                    service.save(project_path, context)
        except NotADirectoryError as exc:
            return ToolResult(success=False, message=str(exc))

        message = format_context_text(context)
        metadata: dict = {
            "context": context.to_dict(),
            "context_path": str(service.context_path(project_path)),
        }
        if debug and trace is not None:
            metadata["detection_trace"] = {
                "detections": trace.detections,
                "ignored": trace.ignored,
            }

        logger.info("Tool context path=%s project=%s", project_path, context.project_name)
        result = ToolResult(success=True, message=message, metadata=metadata)
        if debug and trace is not None:
            from smith.cli.console import get_console

            render_detection_debug(trace, get_console())
        return result


def context_to_json(context: AnalysisProjectContext, health_score: int, issues: list[str]) -> str:
    return json.dumps(build_analysis_json(context, health_score, issues), indent=2)
