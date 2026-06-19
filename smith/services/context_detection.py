import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from smith.tools.fs_utils import (
    collapse_ignored_path,
    should_skip_content_extension,
    should_skip_context_path,
)

logger = logging.getLogger(__name__)

DATABASE_MARKERS = {
    "postgresql": "postgresql",
    "postgres": "postgresql",
    "mysql": "mysql",
    "mariadb": "mariadb",
    "mongodb": "mongodb",
    "redis": "redis",
}

DATABASE_DISPLAY = {
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mariadb": "MariaDB",
    "mongodb": "MongoDB",
    "redis": "Redis",
}

CI_MARKERS = {
    ".github/workflows": "github-actions",
    ".gitlab-ci.yml": "gitlab-ci",
    "Jenkinsfile": "jenkins",
}

CI_DISPLAY = {
    "github-actions": "GitHub Actions",
    "gitlab-ci": "GitLab CI",
    "jenkins": "Jenkins",
}

FRAMEWORK_SLUG_TO_DISPLAY = {
    "spring-boot": "Spring Boot",
    "fastapi": "FastAPI",
    "django": "Django",
    "nestjs": "NestJS",
}

FRAMEWORK_PRIORITY = ("spring-boot", "django", "fastapi", "nestjs")

BUILD_DISPLAY = {
    "poetry": "Poetry",
    "hatch": "Hatch",
    "pdm": "PDM",
    "setuptools": "Setuptools",
    "gradle": "Gradle",
    "gradle-groovy": "Gradle",
    "maven": "Maven",
    "npm": "npm",
    "pnpm": "pnpm",
    "yarn": "yarn",
}

LANGUAGE_DISPLAY = {
    "python": "Python",
    "kotlin": "Kotlin",
    "java": "Java",
    "typescript": "TypeScript",
    "javascript": "JavaScript",
}

INFRA_DISPLAY = {
    "docker": "Docker",
    "docker-compose": "Docker Compose",
    "kubernetes": "Kubernetes",
}

IGNORED_PATH_CAP = 50


@dataclass(slots=True)
class DetectionTrace:
    detections: list[tuple[str, str]] = field(default_factory=list)
    ignored: list[str] = field(default_factory=list)

    def add_detection(self, label: str, reason: str) -> None:
        self.detections.append((label, reason))
        logger.debug("Detected %s because %s", label, reason)

    def record_ignored(self, rel: str) -> None:
        collapsed = collapse_ignored_path(rel)
        if collapsed not in self.ignored and len(self.ignored) < IGNORED_PATH_CAP:
            self.ignored.append(collapsed)


@dataclass(slots=True)
class DetectionResult:
    language: str | None
    framework: str | None
    frameworks: list[str]
    build_system: str | None
    databases: list[str]
    infrastructure: list[str]
    ci_cd: list[str]
    modules: list[str]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _iter_context_files(root: Path, trace: DetectionTrace | None = None) -> list[Path]:
    files: list[Path] = []
    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        if should_skip_context_path(file_path, root):
            if trace is not None:
                try:
                    trace.record_ignored(str(file_path.relative_to(root)))
                except ValueError:
                    pass
            continue
        if should_skip_content_extension(file_path):
            if trace is not None:
                try:
                    trace.record_ignored(str(file_path.relative_to(root)))
                except ValueError:
                    pass
            continue
        files.append(file_path)
    return files


def _has_word(content: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", content, re.IGNORECASE) is not None


def _detect_language(root: Path, trace: DetectionTrace) -> str | None:
    scores: dict[str, int] = {}
    reasons: dict[str, list[str]] = {}

    def add(lang: str, weight: int, reason: str) -> None:
        scores[lang] = scores.get(lang, 0) + weight
        reasons.setdefault(lang, []).append(reason)

    if (root / "pyproject.toml").is_file():
        add("python", 3, "pyproject.toml exists")
    if (root / "setup.py").is_file():
        add("python", 3, "setup.py exists")
    if (root / "setup.cfg").is_file():
        add("python", 2, "setup.cfg exists")
    if (root / "build.gradle.kts").is_file():
        add("kotlin", 3, "build.gradle.kts exists")
    if (root / "pom.xml").is_file():
        add("java", 2, "pom.xml exists")
    if (root / "tsconfig.json").is_file():
        add("typescript", 3, "tsconfig.json exists")
    if (root / "package.json").is_file() and not (root / "tsconfig.json").is_file():
        add("javascript", 2, "package.json exists")

    ext_map = {".py": "python", ".kt": "kotlin", ".java": "java", ".ts": "typescript"}
    file_counts: dict[str, int] = {}
    for file_path in _iter_context_files(root, trace):
        lang = ext_map.get(file_path.suffix.lower())
        if lang:
            file_counts[lang] = file_counts.get(lang, 0) + 1
            scores[lang] = scores.get(lang, 0) + 1

    if not scores:
        return None

    winner = max(scores.items(), key=lambda item: item[1])
    if winner[1] == 0:
        return None

    display = LANGUAGE_DISPLAY.get(winner[0], winner[0].title())
    detail_parts: list[str] = []
    for r in reasons.get(winner[0], []):
        detail_parts.append(r)
    count = file_counts.get(winner[0], 0)
    if count:
        ext = next(k for k, v in ext_map.items() if v == winner[0])
        detail_parts.append(f"{count} {ext} files")
    trace.add_detection(display, ", ".join(detail_parts) or winner[0])
    return winner[0]


def _detect_spring_boot(root: Path, files: list[Path]) -> tuple[str | None, str | None]:
    for name in ("build.gradle", "build.gradle.kts"):
        path = root / name
        if path.is_file():
            content = _read_text(path)
            if "org.springframework.boot" in content or "spring-boot" in content:
                return "spring-boot", f"{name} contains spring-boot plugin/dependency"
    pom = root / "pom.xml"
    if pom.is_file():
        content = _read_text(pom)
        if "spring-boot" in content:
            return "spring-boot", "pom.xml contains spring-boot dependency"
    for file_path in files:
        if file_path.suffix.lower() not in (".java", ".kt"):
            continue
        content = _read_text(file_path)
        if "@SpringBootApplication" in content:
            rel = file_path.relative_to(root)
            return "spring-boot", f"@SpringBootApplication in {rel}"
    return None, None


def _detect_fastapi(root: Path, files: list[Path]) -> tuple[str | None, str | None]:
    for name in ("requirements.txt", "pyproject.toml"):
        path = root / name
        if path.is_file():
            content = _read_text(path).lower()
            if _has_word(content, "fastapi"):
                return "fastapi", f"fastapi dependency in {name}"
    for file_path in files:
        if file_path.suffix.lower() != ".py":
            continue
        content = _read_text(file_path)
        if re.search(r"\bfrom\s+fastapi\b", content) or re.search(r"\bimport\s+fastapi\b", content):
            rel = file_path.relative_to(root)
            return "fastapi", f"FastAPI import in {rel}"
    return None, None


def _detect_django(root: Path) -> tuple[str | None, str | None]:
    manage = root / "manage.py"
    if not manage.is_file():
        return None, None
    for name in ("requirements.txt", "pyproject.toml"):
        path = root / name
        if path.is_file():
            content = _read_text(path).lower()
            if _has_word(content, "django"):
                return "django", f"manage.py and django dependency in {name}"
    return None, None


def _detect_nestjs(root: Path) -> tuple[str | None, str | None]:
    pkg = root / "package.json"
    if not pkg.is_file():
        return None, None
    content = _read_text(pkg)
    if "@nestjs/" in content:
        return "nestjs", "package.json contains @nestjs dependency"
    return None, None


def _detect_frameworks(root: Path, trace: DetectionTrace) -> tuple[str | None, list[str]]:
    files = _iter_context_files(root, trace)
    found: dict[str, str] = {}

    checks: list[tuple[str | None, str | None]] = [
        _detect_spring_boot(root, files),
        _detect_django(root),
        _detect_fastapi(root, files),
        _detect_nestjs(root),
    ]
    for slug, reason in checks:
        if slug and slug not in found:
            found[slug] = reason or slug
            display = FRAMEWORK_SLUG_TO_DISPLAY.get(slug, slug)
            trace.add_detection(display, reason or slug)

    frameworks = [
        FRAMEWORK_SLUG_TO_DISPLAY.get(slug, slug) for slug in FRAMEWORK_PRIORITY if slug in found
    ]
    primary = next((slug for slug in FRAMEWORK_PRIORITY if slug in found), None)
    return primary, frameworks


def _detect_build_system(root: Path, trace: DetectionTrace) -> str | None:
    pyproject = root / "pyproject.toml"
    pyproject_text = _read_text(pyproject) if pyproject.is_file() else ""

    if pyproject.is_file() and "[tool.poetry]" in pyproject_text:
        trace.add_detection("Poetry", "pyproject.toml contains [tool.poetry]")
        return "poetry"
    if pyproject.is_file() and "[tool.pdm]" in pyproject_text:
        trace.add_detection("PDM", "pyproject.toml contains [tool.pdm]")
        return "pdm"
    if pyproject.is_file() and ("[tool.hatch" in pyproject_text or "hatchling" in pyproject_text):
        trace.add_detection("Hatch", "pyproject.toml uses hatch/hatchling")
        return "hatch"
    if (root / "build.gradle.kts").is_file():
        trace.add_detection("Gradle", "build.gradle.kts exists")
        return "gradle"
    if (root / "pom.xml").is_file():
        trace.add_detection("Maven", "pom.xml exists")
        return "maven"
    if (root / "build.gradle").is_file():
        trace.add_detection("Gradle", "build.gradle exists")
        return "gradle-groovy"
    if (root / "pnpm-lock.yaml").is_file():
        trace.add_detection("pnpm", "pnpm-lock.yaml exists")
        return "pnpm"
    if (root / "yarn.lock").is_file():
        trace.add_detection("yarn", "yarn.lock exists")
        return "yarn"
    if pyproject.is_file() and "[project]" in pyproject_text:
        trace.add_detection("Setuptools", "pyproject.toml contains [project]")
        return "setuptools"
    if (root / "setup.py").is_file():
        trace.add_detection("Setuptools", "setup.py exists")
        return "setuptools"
    if (root / "package.json").is_file():
        trace.add_detection("npm", "package.json exists")
        return "npm"
    return None


def _detect_databases(root: Path, trace: DetectionTrace) -> list[str]:
    found: set[str] = set()
    config_names = {
        "application.yml",
        "application.yaml",
        "application.properties",
        "docker-compose.yml",
        "docker-compose.yaml",
        "compose.yml",
    }
    candidates: list[Path] = []
    for name in config_names:
        path = root / name
        if path.is_file() and not should_skip_context_path(path, root):
            candidates.append(path)

    for file_path in candidates:
        content = _read_text(file_path).lower()
        for marker, slug in DATABASE_MARKERS.items():
            if _has_word(content, marker):
                found.add(slug)
                display = DATABASE_DISPLAY.get(slug, slug)
                trace.add_detection(display, f"{file_path.name} contains {marker}")

    return sorted(found)


def _detect_infrastructure(root: Path, trace: DetectionTrace) -> list[str]:
    found: set[str] = set()

    if (root / "Dockerfile").is_file():
        found.add("docker")
        trace.add_detection("Docker", "Dockerfile at project root")

    for name in ("docker-compose.yml", "docker-compose.yaml", "compose.yml"):
        if (root / name).is_file():
            found.add("docker-compose")
            trace.add_detection("Docker Compose", f"{name} at project root")
            break

    for pattern in ("*.yml", "*.yaml"):
        for file_path in root.glob(pattern):
            if not file_path.is_file():
                continue
            content = _read_text(file_path).lower()
            if "apiversion:" in content:
                found.add("kubernetes")
                trace.add_detection("Kubernetes", f"{file_path.name} contains apiVersion")
                break
        if "kubernetes" in found:
            break

    return sorted(found)


def _detect_ci_cd(root: Path, trace: DetectionTrace) -> list[str]:
    found: set[str] = set()
    for marker, slug in CI_MARKERS.items():
        if (root / marker).exists():
            found.add(slug)
            display = CI_DISPLAY.get(slug, slug)
            trace.add_detection(display, f"{marker} exists")
    return sorted(found)


def _detect_modules(root: Path, trace: DetectionTrace) -> list[str]:
    modules: set[str] = set()
    for build_file in ("build.gradle.kts", "build.gradle", "pom.xml"):
        for bf in root.rglob(build_file):
            if should_skip_context_path(bf, root):
                continue
            if bf.parent != root:
                modules.add(bf.parent.name)
    if modules:
        trace.add_detection("Modules", f"{len(modules)} sub-module build files")
    return sorted(modules)


def detect_project_context(
    root: Path, *, debug: bool = False
) -> tuple[DetectionResult, DetectionTrace]:
    root = root.expanduser().resolve()
    trace = DetectionTrace()

    language = _detect_language(root, trace)
    framework, frameworks = _detect_frameworks(root, trace)
    build_system = _detect_build_system(root, trace)
    databases = _detect_databases(root, trace)
    infrastructure = _detect_infrastructure(root, trace)
    ci_cd = _detect_ci_cd(root, trace)
    modules = _detect_modules(root, trace)

    result = DetectionResult(
        language=language,
        framework=framework,
        frameworks=frameworks,
        build_system=build_system,
        databases=databases,
        infrastructure=infrastructure,
        ci_cd=ci_cd,
        modules=modules,
    )
    return result, trace
