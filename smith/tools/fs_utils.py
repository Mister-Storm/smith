from pathlib import Path

SKIP_DIR_NAMES = {
    ".git",
    "node_modules",
    "target",
    "build",
    ".gradle",
    "__pycache__",
    ".venv",
    "venv",
}

SKIP_CONTEXT_DIRS = SKIP_DIR_NAMES | {
    "docs",
    ".smith",
    ".msmith",
    "dist",
    "coverage",
    "htmlcov",
    ".pytest_cache",
}

SKIP_CONTEXT_TEST_SEGMENTS = {"test", "tests"}

TRUSTED_DEPENDENCY_FILES = {
    "pyproject.toml",
    "requirements.txt",
    "setup.py",
    "setup.cfg",
    "package.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "build.gradle",
    "build.gradle.kts",
    "pom.xml",
    "manage.py",
}

SKIP_CONTENT_EXTENSIONS = {".md", ".txt", ".log", ".json"}


def should_skip_path(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return True
    return any(part.startswith(".") or part in SKIP_DIR_NAMES for part in rel.parts)


def _is_github_template_path(rel: Path) -> bool:
    parts = rel.parts
    if len(parts) >= 2 and parts[0] == ".github":
        return parts[1] in ("ISSUE_TEMPLATE", "PULL_REQUEST_TEMPLATE")
    return False


def should_skip_context_path(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return True
    if _is_github_template_path(rel):
        return True
    for part in rel.parts:
        if part in SKIP_CONTEXT_DIRS:
            return True
        if part in SKIP_CONTEXT_TEST_SEGMENTS:
            return True
        if part == "src" and len(rel.parts) > rel.parts.index("src") + 1:
            idx = rel.parts.index("src")
            if idx + 1 < len(rel.parts) and rel.parts[idx + 1] == "test":
                return True
    return False


def is_trusted_dependency_file(path: Path) -> bool:
    return path.name in TRUSTED_DEPENDENCY_FILES


def should_skip_content_extension(path: Path) -> bool:
    if is_trusted_dependency_file(path):
        return False
    return path.suffix.lower() in SKIP_CONTENT_EXTENSIONS


def collapse_ignored_path(rel: str) -> str:
    prefixes = (
        "docs/",
        "tests/",
        "test/",
        ".git/",
        ".venv/",
        "dist/",
        ".pytest_cache/",
        ".smith/",
        "__pycache__/",
    )
    for prefix in prefixes:
        bare = prefix.rstrip("/")
        if rel == bare or rel.startswith(prefix):
            return prefix
        if f"/{bare}/" in f"/{rel}/":
            return prefix
    return rel


def format_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    if n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{n / (1024 * 1024 * 1024):.2f} GB"
