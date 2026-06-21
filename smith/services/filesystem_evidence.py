"""Depth-aware filesystem evidence collection for investigative assistant."""

from __future__ import annotations

from pathlib import Path

from smith.models.assistant import EvidenceItem, EvidenceLevel, InvestigationDepth
from smith.tools.fs_utils import (
    TRUSTED_DEPENDENCY_FILES,
    should_skip_context_path,
    should_skip_path,
)

MAX_FILE_SIZE = 8000

_DEPTH_FILE_LIMITS: dict[InvestigationDepth, int] = {
    InvestigationDepth.QUICK: 8,
    InvestigationDepth.STANDARD: 20,
    InvestigationDepth.DEEP: 40,
}

_BUILD_FILES = frozenset(
    {
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "requirements.txt",
        "package.json",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "settings.gradle",
        "settings.gradle.kts",
        "Cargo.toml",
        "go.mod",
        "Makefile",
        "docker-compose.yml",
        "docker-compose.yaml",
        "Dockerfile",
    }
)

_CONFIG_GLOBS = (
    "**/application.yml",
    "**/application.yaml",
    "**/application.properties",
    "**/application*.yml",
    "**/.env.example",
    "**/config/*.yml",
    "**/config/*.yaml",
)

_SOURCE_NAME_HINTS = (
    "service",
    "controller",
    "repository",
    "repo",
    "usecase",
    "use_case",
    "handler",
    "adapter",
    "port",
    "domain",
    "application",
    "infrastructure",
)

_SOURCE_EXTENSIONS = frozenset(
    {".py", ".java", ".kt", ".kts", ".go", ".rs", ".ts", ".tsx", ".js", ".jsx"}
)


def _read_file(path: Path, limit: int = MAX_FILE_SIZE) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def _evidence_item(
    *,
    source: str,
    summary: str,
    detail: str,
    path: Path,
    level: EvidenceLevel,
    extra_meta: dict | None = None,
) -> EvidenceItem:
    meta = {"evidence_level": level.value}
    if extra_meta:
        meta.update(extra_meta)
    return EvidenceItem(
        source=source,
        summary=summary,
        detail=detail,
        path=str(path),
        metadata=meta,
    )


def collect_structure(repo: Path, depth: InvestigationDepth) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    if not repo.is_dir():
        return items

    entries: list[str] = []
    try:
        for child in sorted(repo.iterdir()):
            if child.name.startswith(".") and child.name not in (".github",):
                continue
            if child.is_dir():
                entries.append(f"{child.name}/")
            else:
                entries.append(child.name)
    except OSError:
        return items

    tree_text = "\n".join(entries[:80])
    items.append(
        _evidence_item(
            source="filesystem",
            summary=f"Root structure of {repo.name}",
            detail=tree_text,
            path=repo,
            level=EvidenceLevel.STRUCTURE,
            extra_meta={"entry_count": len(entries)},
        )
    )

    readme = _find_readme(repo)
    if readme:
        content = _read_file(readme)
        items.append(
            _evidence_item(
                source="filesystem",
                summary=f"README ({readme.name})",
                detail=content,
                path=readme,
                level=EvidenceLevel.STRUCTURE,
            )
        )

    if depth != InvestigationDepth.QUICK:
        modules = _detect_modules(repo)
        if modules:
            items.append(
                _evidence_item(
                    source="filesystem",
                    summary=f"Detected modules ({len(modules)})",
                    detail="\n".join(modules),
                    path=repo,
                    level=EvidenceLevel.STRUCTURE,
                    extra_meta={"modules": modules},
                )
            )
    return items


def collect_configuration(repo: Path, depth: InvestigationDepth) -> list[EvidenceItem]:
    if depth == InvestigationDepth.QUICK:
        return _collect_build_files(repo, limit=4)
    items = _collect_build_files(repo, limit=8)
    for pattern in _CONFIG_GLOBS:
        for path in repo.glob(pattern):
            if should_skip_path(path, repo):
                continue
            if path.is_file() and path.stat().st_size <= MAX_FILE_SIZE * 4:
                items.append(
                    _evidence_item(
                        source="filesystem",
                        summary=f"Configuration: {path.relative_to(repo)}",
                        detail=_read_file(path),
                        path=path,
                        level=EvidenceLevel.CONFIGURATION,
                    )
                )
            if len(items) >= 12:
                break
    ci_items = _collect_ci_files(repo)
    items.extend(ci_items)
    return items[:15]


def collect_source_samples(repo: Path, depth: InvestigationDepth) -> list[EvidenceItem]:
    limit = _DEPTH_FILE_LIMITS[depth]
    candidates = _rank_source_files(repo, depth)
    items: list[EvidenceItem] = []
    for path in candidates[:limit]:
        content = _read_file(path)
        if not content.strip():
            continue
        rel = path.relative_to(repo)
        items.append(
            _evidence_item(
                source="filesystem",
                summary=f"Source sample: {rel}",
                detail=content,
                path=path,
                level=EvidenceLevel.SOURCE_CODE,
                extra_meta={"relative_path": str(rel)},
            )
        )
    return items


def collect_all_for_depth(repo: Path, depth: InvestigationDepth) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    items.extend(collect_structure(repo, depth))
    if depth != InvestigationDepth.QUICK:
        items.extend(collect_configuration(repo, depth))
    if depth in (InvestigationDepth.STANDARD, InvestigationDepth.DEEP):
        items.extend(collect_source_samples(repo, depth))
    if depth == InvestigationDepth.DEEP:
        items.extend(_collect_dependency_hints(repo))
    return items


def _find_readme(repo: Path) -> Path | None:
    for name in ("README.md", "README.rst", "README.txt", "README"):
        path = repo / name
        if path.is_file():
            return path
    return None


def _collect_build_files(repo: Path, *, limit: int) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for name in _BUILD_FILES:
        path = repo / name
        if path.is_file():
            items.append(
                _evidence_item(
                    source="filesystem",
                    summary=f"Build file: {name}",
                    detail=_read_file(path),
                    path=path,
                    level=EvidenceLevel.CONFIGURATION,
                )
            )
        if len(items) >= limit:
            break
    for path in repo.rglob("*"):
        if path.name in TRUSTED_DEPENDENCY_FILES and path.parent != repo:
            if should_skip_path(path, repo):
                continue
            items.append(
                _evidence_item(
                    source="filesystem",
                    summary=f"Build file: {path.relative_to(repo)}",
                    detail=_read_file(path),
                    path=path,
                    level=EvidenceLevel.CONFIGURATION,
                )
            )
            if len(items) >= limit:
                break
    return items


def _collect_ci_files(repo: Path) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    ci_dirs = [repo / ".github" / "workflows", repo / ".gitlab-ci.yml"]
    workflows = repo / ".github" / "workflows"
    if workflows.is_dir():
        for wf in sorted(workflows.glob("*.yml"))[:3]:
            items.append(
                _evidence_item(
                    source="filesystem",
                    summary=f"CI workflow: {wf.name}",
                    detail=_read_file(wf),
                    path=wf,
                    level=EvidenceLevel.CONFIGURATION,
                )
            )
    gitlab = repo / ".gitlab-ci.yml"
    if gitlab.is_file():
        items.append(
            _evidence_item(
                source="filesystem",
                summary="GitLab CI configuration",
                detail=_read_file(gitlab),
                path=gitlab,
                level=EvidenceLevel.CONFIGURATION,
            )
        )
    for path in ci_dirs:
        if path.is_file():
            items.append(
                _evidence_item(
                    source="filesystem",
                    summary=f"CI config: {path.name}",
                    detail=_read_file(path),
                    path=path,
                    level=EvidenceLevel.CONFIGURATION,
                )
            )
    return items


def _detect_modules(repo: Path) -> list[str]:
    modules: list[str] = []
    settings = repo / "settings.gradle.kts"
    if not settings.is_file():
        settings = repo / "settings.gradle"
    if settings.is_file():
        text = _read_file(settings, limit=4000)
        for line in text.splitlines():
            stripped = line.strip()
            if "include(" in stripped or "include '" in stripped:
                token = stripped.split("(")[-1].split(")")[0].strip("'\": ")
                if token:
                    modules.append(token.replace(":", "/"))
    if (repo / "pom.xml").is_file() and not modules:
        for child in repo.iterdir():
            if child.is_dir() and (child / "pom.xml").is_file():
                modules.append(child.name)
    if not modules:
        for marker in ("pyproject.toml", "package.json"):
            if (repo / marker).is_file():
                for child in repo.iterdir():
                    if child.is_dir() and not child.name.startswith("."):
                        if any(child.rglob("*")):
                            modules.append(child.name)
                break
    return sorted(set(modules))[:20]


def _rank_source_files(repo: Path, depth: InvestigationDepth) -> list[Path]:
    scored: list[tuple[int, Path]] = []
    max_walk = 500 if depth == InvestigationDepth.DEEP else 300
    count = 0
    for path in repo.rglob("*"):
        if count >= max_walk:
            break
        count += 1
        if not path.is_file() or path.suffix not in _SOURCE_EXTENSIONS:
            continue
        if should_skip_context_path(path, repo):
            continue
        rel = str(path.relative_to(repo)).lower()
        score = 0
        for hint in _SOURCE_NAME_HINTS:
            if hint in rel:
                score += 3
        if depth == InvestigationDepth.DEEP and any(
            seg in rel for seg in ("domain", "application", "infrastructure", "adapter", "port")
        ):
            score += 2
        scored.append((score, path))
    scored.sort(key=lambda pair: (-pair[0], str(pair[1])))
    return [path for _, path in scored]


def _collect_dependency_hints(repo: Path) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for name in ("settings.gradle.kts", "settings.gradle", "pom.xml"):
        path = repo / name
        if path.is_file():
            items.append(
                _evidence_item(
                    source="filesystem",
                    summary=f"Module dependencies ({name})",
                    detail=_read_file(path, limit=6000),
                    path=path,
                    level=EvidenceLevel.STRUCTURE,
                )
            )
    return items
