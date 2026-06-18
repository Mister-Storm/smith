import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

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

DATABASE_MARKERS = {
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "mysql": "MySQL",
    "mariadb": "MariaDB",
    "h2": "H2",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "sqlite": "SQLite",
    "flyway": "Flyway",
    "liquibase": "Liquibase",
}

CI_MARKERS = {
    ".github/workflows": "GitHub Actions",
    ".gitlab-ci.yml": "GitLab CI",
    "Jenkinsfile": "Jenkins",
    "azure-pipelines.yml": "Azure Pipelines",
    ".circleci": "CircleCI",
}


@dataclass(slots=True)
class ProjectContext:
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
    def from_dict(cls, data: dict) -> "ProjectContext":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _detect_languages(path: Path) -> list[str]:
    counts: dict[str, int] = {}
    ext_map = {".kt": "Kotlin", ".java": "Java", ".py": "Python", ".go": "Go", ".rs": "Rust"}
    for file_path in path.rglob("*"):
        if not file_path.is_file() or should_skip_path(file_path, path):
            continue
        lang = ext_map.get(file_path.suffix.lower())
        if lang:
            counts[lang] = counts.get(lang, 0) + 1
    return [lang for lang, _ in sorted(counts.items(), key=lambda x: -x[1])]


def _detect_build_system(path: Path) -> str | None:
    if (path / "build.gradle.kts").is_file():
        return "Gradle Kotlin DSL"
    if (path / "pom.xml").is_file():
        return "Maven"
    if (path / "build.gradle").is_file():
        return "Gradle"
    if (path / "pyproject.toml").is_file() or (path / "setup.py").is_file():
        return "Python (pyproject/setup)"
    return None


def _detect_frameworks(path: Path) -> list[str]:
    frameworks: set[str] = set()
    for file_path in path.rglob("*"):
        if not file_path.is_file() or should_skip_path(file_path, path):
            continue
        if file_path.suffix not in (".gradle", ".kts", ".xml", ".java", ".kt", ".py"):
            if file_path.name not in ("pom.xml", "build.gradle", "build.gradle.kts"):
                continue
        content = _read_text(file_path)
        if "spring-boot-starter" in content or "@SpringBootApplication" in content:
            frameworks.add("Spring Boot")
        if "quarkus" in content.lower():
            frameworks.add("Quarkus")
        if "micronaut" in content.lower():
            frameworks.add("Micronaut")
        if "django" in content.lower():
            frameworks.add("Django")
        if "fastapi" in content.lower():
            frameworks.add("FastAPI")
    return sorted(frameworks)


def _detect_databases(path: Path) -> list[str]:
    found: set[str] = set()
    for file_path in path.rglob("*"):
        if not file_path.is_file() or should_skip_path(file_path, path):
            continue
        if file_path.suffix not in (
            ".gradle",
            ".kts",
            ".xml",
            ".yml",
            ".yaml",
            ".properties",
            ".env",
            ".java",
            ".kt",
        ):
            continue
        content = _read_text(file_path).lower()
        for marker, name in DATABASE_MARKERS.items():
            if marker in content:
                found.add(name)
    return sorted(found)


def _detect_containers(path: Path) -> list[str]:
    containers: set[str] = set()
    for name in ("Dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml"):
        if (path / name).is_file() or any(
            p.name == name for p in path.rglob(name) if not should_skip_path(p, path)
        ):
            containers.add("Docker")
            break
    if (path / "kubernetes").is_dir() or any(
        p.name.endswith((".yaml", ".yml"))
        and "kind:" in _read_text(p)
        and not should_skip_path(p, path)
        for p in path.rglob("*.yml")
    ):
        containers.add("Kubernetes")
    return sorted(containers)


def _detect_ci_cd(path: Path) -> list[str]:
    found: set[str] = set()
    for marker, name in CI_MARKERS.items():
        target = path / marker
        if target.exists():
            found.add(name)
    return sorted(found)


def _detect_modules(path: Path) -> list[str]:
    modules: set[str] = set()
    for build_file in ("build.gradle.kts", "build.gradle", "pom.xml"):
        for bf in path.rglob(build_file):
            if should_skip_path(bf, path):
                continue
            if bf.parent != path:
                modules.add(bf.parent.name)
    return sorted(modules)


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


def _detect_patterns(context: ProjectContext) -> list[str]:
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


def generate_project_context(project_path: Path) -> ProjectContext:
    path = project_path.expanduser().resolve()
    languages = _detect_languages(path)
    build_system = _detect_build_system(path)
    has_build = build_system is not None

    context = ProjectContext(
        language=languages[0] if languages else None,
        frameworks=_detect_frameworks(path),
        build_system=build_system,
        databases=_detect_databases(path),
        containers=_detect_containers(path),
        ci_cd=_detect_ci_cd(path),
        modules=_detect_modules(path),
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


def compute_health_score(context: ProjectContext) -> tuple[int, list[str]]:
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


def generate_architecture_observations(context: ProjectContext) -> str:
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


def context_to_markdown(context: ProjectContext) -> str:
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


def build_analysis_json(context: ProjectContext, health_score: int, issues: list[str]) -> dict:
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
        project_path = Path(kwargs["path"]).expanduser().resolve()
        save = bool(kwargs.get("save", True))

        if not project_path.is_dir():
            return ToolResult(success=False, message=f"Not a directory: {project_path}")

        context = generate_project_context(project_path)
        health_score, issues = compute_health_score(context)
        markdown = context_to_markdown(context)
        health_section = f"\n## Project Health\n\nScore: {health_score}/100\n"
        message = markdown + health_section

        metadata = {
            "health_score": health_score,
            "issues": issues,
            "context": context.to_dict(),
        }

        if save and kwargs.get("store"):
            kwargs["store"].save(context)

        logger.info("Tool context path=%s score=%d", project_path, health_score)
        return ToolResult(success=True, message=message, metadata=metadata)


def context_to_json(context: ProjectContext, health_score: int, issues: list[str]) -> str:
    return json.dumps(build_analysis_json(context, health_score, issues), indent=2)
