import logging
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from smith.models.project_context import ProjectContext
from smith.tools.fs_utils import should_skip_path

logger = logging.getLogger(__name__)

CONTEXT_DIR = ".smith"
CONTEXT_FILE = "project_context.json"

DATABASE_MARKERS = {
    "postgresql": "postgresql",
    "postgres": "postgresql",
    "mysql": "mysql",
    "mariadb": "mariadb",
    "mongodb": "mongodb",
    "redis": "redis",
}

CI_MARKERS = {
    ".github/workflows": "github-actions",
    ".gitlab-ci.yml": "gitlab-ci",
    "Jenkinsfile": "jenkins",
}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _slug(value: str) -> str:
    return value.lower().replace(" ", "-")


def _display_language(slug: str | None) -> str:
    mapping = {
        "kotlin": "Kotlin",
        "java": "Java",
        "python": "Python",
        "javascript": "JavaScript",
        "typescript": "TypeScript",
    }
    if not slug:
        return "Unknown"
    return mapping.get(slug, slug.title())


def _display_framework(slug: str | None) -> str:
    mapping = {
        "spring-boot": "Spring Boot",
        "fastapi": "FastAPI",
        "django": "Django",
        "nestjs": "NestJS",
    }
    if not slug:
        return "Unknown"
    return mapping.get(slug, slug.replace("-", " ").title())


def _display_build(slug: str | None) -> str:
    mapping = {
        "gradle": "Gradle Kotlin DSL",
        "gradle-groovy": "Gradle",
        "maven": "Maven",
        "python": "Python (pyproject/setup)",
        "npm": "npm",
    }
    if not slug:
        return "Unknown"
    return mapping.get(slug, slug.title())


def _display_database(slug: str) -> str:
    mapping = {
        "postgresql": "PostgreSQL",
        "mysql": "MySQL",
        "mariadb": "MariaDB",
        "mongodb": "MongoDB",
        "redis": "Redis",
    }
    return mapping.get(slug, slug.replace("-", " ").title())


def _display_infra(slug: str) -> str:
    mapping = {
        "docker": "Docker",
        "docker-compose": "Docker Compose",
        "kubernetes": "Kubernetes",
    }
    return mapping.get(slug, slug.replace("-", " ").title())


def _display_ci(slug: str) -> str:
    mapping = {
        "github-actions": "GitHub Actions",
        "gitlab-ci": "GitLab CI",
        "jenkins": "Jenkins",
    }
    return mapping.get(slug, slug.replace("-", " ").title())


class ProjectContextService:
    @staticmethod
    def context_path(project_root: Path) -> Path:
        return project_root.expanduser().resolve() / CONTEXT_DIR / CONTEXT_FILE

    def build(self, path: Path) -> ProjectContext:
        root = path.expanduser().resolve()
        if not root.is_dir():
            raise NotADirectoryError(f"Not a directory: {root}")

        language = self._detect_language(root)
        framework = self._detect_framework(root)
        build_system = self._detect_build_system(root)

        return ProjectContext(
            project_name=root.name,
            language=language,
            framework=framework,
            build_system=build_system,
            database=self._detect_databases(root),
            infrastructure=self._detect_infrastructure(root),
            ci_cd=self._detect_ci_cd(root),
            modules=self._detect_modules(root),
            generated_at=datetime.now(UTC),
        )

    def load(self, path: Path) -> ProjectContext | None:
        context_file = self.context_path(path)
        if not context_file.is_file():
            return None
        try:
            return ProjectContext.from_json(context_file.read_text(encoding="utf-8"))
        except (OSError, ValueError, KeyError) as exc:
            logger.warning("Failed to load project context from %s: %s", context_file, exc)
            return None

    def save(self, path: Path, context: ProjectContext) -> Path:
        context_file = self.context_path(path)
        context_file.parent.mkdir(parents=True, exist_ok=True)
        context_file.write_text(context.to_json(), encoding="utf-8")
        logger.info("Saved project context to %s", context_file)
        return context_file

    def refresh(self, path: Path) -> ProjectContext:
        context = self.build(path)
        self.save(path, context)
        return context

    def _detect_language(self, root: Path) -> str | None:
        signals: dict[str, int] = {}

        if (root / "build.gradle.kts").is_file():
            signals["kotlin"] = signals.get("kotlin", 0) + 3
        if (root / "pyproject.toml").is_file() or (root / "requirements.txt").is_file():
            signals["python"] = signals.get("python", 0) + 3
        if (root / "package.json").is_file():
            signals["javascript"] = signals.get("javascript", 0) + 2
        if (root / "tsconfig.json").is_file():
            signals["typescript"] = signals.get("typescript", 0) + 3

        for file_path in root.rglob("*"):
            if not file_path.is_file() or should_skip_path(file_path, root):
                continue
            if file_path.suffix == ".kt":
                signals["kotlin"] = signals.get("kotlin", 0) + 1
            elif file_path.suffix == ".java":
                signals["java"] = signals.get("java", 0) + 1

        if not signals:
            return None
        return max(signals.items(), key=lambda item: item[1])[0]

    def _detect_framework(self, root: Path) -> str | None:
        for file_path in root.rglob("*"):
            if not file_path.is_file() or should_skip_path(file_path, root):
                continue
            suffixes = (".gradle", ".kts", ".xml", ".java", ".kt", ".py", ".ts", ".js")
            if file_path.suffix not in suffixes:
                if file_path.name not in (
                    "pom.xml",
                    "build.gradle",
                    "build.gradle.kts",
                    "package.json",
                    "manage.py",
                ):
                    continue
            content = _read_text(file_path)
            lower = content.lower()
            if "spring-boot-starter" in content or "@SpringBootApplication" in content:
                return "spring-boot"
            if "fastapi" in lower or "from fastapi" in lower:
                return "fastapi"
            if file_path.name == "manage.py" or "django" in lower:
                return "django"
            if "@nestjs" in content or "nestjs" in lower:
                return "nestjs"
        return None

    def _detect_build_system(self, root: Path) -> str | None:
        if (root / "build.gradle.kts").is_file():
            return "gradle"
        if (root / "pom.xml").is_file():
            return "maven"
        if (root / "build.gradle").is_file():
            return "gradle-groovy"
        if (root / "pyproject.toml").is_file() or (root / "setup.py").is_file():
            return "python"
        if (root / "package.json").is_file():
            return "npm"
        return None

    def _detect_databases(self, root: Path) -> list[str]:
        found: set[str] = set()
        config_names = (
            "application.yml",
            "application.yaml",
            "application.properties",
            "docker-compose.yml",
            "docker-compose.yaml",
            "compose.yml",
        )
        for file_path in root.rglob("*"):
            if not file_path.is_file() or should_skip_path(file_path, root):
                continue
            if file_path.name not in config_names and file_path.suffix not in (
                ".yml",
                ".yaml",
                ".properties",
            ):
                continue
            content = _read_text(file_path).lower()
            for marker, name in DATABASE_MARKERS.items():
                if marker in content:
                    found.add(name)
        return sorted(found)

    def _detect_infrastructure(self, root: Path) -> list[str]:
        found: set[str] = set()
        if (root / "Dockerfile").is_file() or any(
            p.name == "Dockerfile"
            for p in root.rglob("Dockerfile")
            if not should_skip_path(p, root)
        ):
            found.add("docker")
        for name in ("docker-compose.yml", "docker-compose.yaml", "compose.yml"):
            if (root / name).is_file() or any(
                p.name == name for p in root.rglob(name) if not should_skip_path(p, root)
            ):
                found.add("docker-compose")
                break
        for file_path in root.rglob("*.yml"):
            if should_skip_path(file_path, root):
                continue
            if "apiversion:" in _read_text(file_path).lower():
                found.add("kubernetes")
                break
        for file_path in root.rglob("*.yaml"):
            if should_skip_path(file_path, root):
                continue
            if "apiversion:" in _read_text(file_path).lower():
                found.add("kubernetes")
                break
        return sorted(found)

    def _detect_ci_cd(self, root: Path) -> list[str]:
        found: set[str] = set()
        for marker, name in CI_MARKERS.items():
            if (root / marker).exists():
                found.add(name)
        return sorted(found)

    def _detect_modules(self, root: Path) -> list[str]:
        modules: set[str] = set()
        for build_file in ("build.gradle.kts", "build.gradle", "pom.xml"):
            for bf in root.rglob(build_file):
                if should_skip_path(bf, root):
                    continue
                if bf.parent != root:
                    modules.add(bf.parent.name)
        return sorted(modules)


def format_context_text(context: ProjectContext) -> str:
    generated = context.generated_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")

    def bullet_list(items: list[str], *, formatter=str) -> str:
        if not items:
            return "- None detected"
        return "\n".join(f"- {formatter(i)}" for i in items)

    lines = [
        f"Project: {context.project_name}",
        "",
        "Language:",
        bullet_list([context.language] if context.language else [], formatter=_display_language),
        "",
        "Framework:",
        bullet_list([context.framework] if context.framework else [], formatter=_display_framework),
        "",
        "Build:",
        bullet_list(
            [context.build_system] if context.build_system else [], formatter=_display_build
        ),
        "",
        "Database:",
        bullet_list(context.database, formatter=_display_database),
        "",
        "Infrastructure:",
        bullet_list(context.infrastructure, formatter=_display_infra),
        "",
        "CI/CD:",
        bullet_list(context.ci_cd, formatter=_display_ci),
        "",
        "Modules:",
        bullet_list(context.modules),
        "",
        f"Generated:\n{generated}",
    ]
    return "\n".join(lines)


def render_context_tables(context: ProjectContext, console: Console) -> None:
    console.print(f"\n[bold]Project:[/bold] {context.project_name}\n")

    summary = Table(show_header=True, header_style="bold", title="Project Context")
    summary.add_column("Field", style="dim")
    summary.add_column("Value")

    summary.add_row("Language", _display_language(context.language))
    summary.add_row("Framework", _display_framework(context.framework))
    summary.add_row("Database", ", ".join(_display_database(d) for d in context.database) or "—")
    summary.add_row("Build System", _display_build(context.build_system))
    summary.add_row(
        "Infrastructure",
        ", ".join(_display_infra(i) for i in context.infrastructure) or "—",
    )
    summary.add_row("CI/CD", ", ".join(_display_ci(c) for c in context.ci_cd) or "—")
    generated = context.generated_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
    summary.add_row("Generated", generated)
    console.print(summary)

    if context.modules:
        modules = Table(show_header=True, header_style="bold", title="Modules")
        modules.add_column("Module")
        for module in context.modules:
            modules.add_row(module)
        console.print()
        console.print(modules)
