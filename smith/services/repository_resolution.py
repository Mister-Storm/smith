"""Resolve repository references from user messages."""

from __future__ import annotations

from pathlib import Path

from smith.models.assistant import AssistantSession, ResolveResult, ResolveStatus
from smith.services.intent_detection import REPOSITORY_NAME_STOP_WORDS
from smith.services.workspace_intelligence import PROJECT_FILE_MARKERS

_LEVENSHTEIN_MAX = 2
_NEARBY_SCAN_CAP = 20


def _log_resolution_match(ref: str, source: str, path: Path) -> None:
    from smith.services.investigation_trace import log_resolution_match

    log_resolution_match(ref, source, path)


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


def is_repository_name_ref(ref: str) -> bool:
    ref = ref.strip()
    if not ref:
        return False
    if ref.startswith("./") or ref.startswith("../") or ref.startswith("~"):
        return False
    if Path(ref).expanduser().is_absolute():
        return False
    if Path(ref).suffix:
        return False
    return True


def is_likely_repository_name_ref(ref: str) -> bool:
    ref = ref.strip()
    if not is_repository_name_ref(ref):
        return False
    if len(ref) < 2:
        return False
    return ref.lower() not in REPOSITORY_NAME_STOP_WORDS


def is_project_directory(path: Path) -> bool:
    if not path.is_dir():
        return False
    has_markers = any((path / marker).exists() for marker in PROJECT_FILE_MARKERS)
    return has_markers or (path / ".git").is_dir()


def discover_nearby_projects(cwd: Path, *, depth: int = 1) -> list[Path]:
    """Projects in cwd.parent (siblings) plus a shallow scan under the parent."""
    cwd = cwd.expanduser().resolve()
    found: list[Path] = []
    seen: set[Path] = set()

    def add(path: Path) -> None:
        resolved = path.expanduser().resolve()
        if resolved in seen or not is_project_directory(resolved):
            return
        seen.add(resolved)
        found.append(resolved)

    try:
        for child in cwd.parent.iterdir():
            if child.is_dir():
                add(child)
    except OSError:
        pass

    if depth >= 1:
        count = 0
        try:
            for sibling in cwd.parent.iterdir():
                if not sibling.is_dir() or count >= _NEARBY_SCAN_CAP:
                    continue
                try:
                    for nested in sibling.iterdir():
                        if nested.is_dir():
                            add(nested)
                            count += 1
                            if count >= _NEARBY_SCAN_CAP:
                                break
                except OSError:
                    continue
                if count >= _NEARBY_SCAN_CAP:
                    break
        except OSError:
            pass

    return found


def format_not_found_response(
    ref: str,
    suggestions: list[str],
    *,
    nearby_projects: list[Path] | None = None,
) -> str:
    lines = ["Repository not found.", ""]
    if suggestions:
        lines.append("Similar repositories:")
        for name in suggestions[:5]:
            lines.append(f"* {name}")
        lines.append("")
        if len(suggestions) == 1:
            lines.append(f"Did you mean {suggestions[0]}?")
        else:
            lines.append(f"Did you mean one of: {', '.join(suggestions[:3])}?")
        lines.append("")

    if nearby_projects:
        lines.append("Projects found nearby:")
        for project in nearby_projects[:8]:
            lines.append(f"* {project.name}  ({project})")
    return "\n".join(lines).rstrip()


def _collect_name_candidates(
    *,
    cwd: Path,
    session: AssistantSession | None,
    workspace_projects: list[Path] | None,
) -> dict[str, Path]:
    names: dict[str, Path] = {}
    for project in discover_nearby_projects(cwd):
        names.setdefault(project.name, project)
    if workspace_projects:
        for project in workspace_projects:
            if is_project_directory(project):
                names.setdefault(project.name, project.resolve())
    if session:
        for recent in session.recent_repositories:
            if is_project_directory(recent):
                names.setdefault(recent.name, recent.resolve())
    return names


def _similar_names(ref: str, candidates: dict[str, Path]) -> list[str]:
    matches: list[tuple[int, str]] = []
    ref_lower = ref.lower()
    for name in candidates:
        distance = _levenshtein(ref_lower, name.lower())
        if distance <= _LEVENSHTEIN_MAX:
            matches.append((distance, name))
    matches.sort(key=lambda pair: (pair[0], pair[1].lower()))
    return [name for _, name in matches]


def _resolve_bare_name(
    ref: str,
    *,
    cwd: Path,
    session: AssistantSession | None,
    workspace_projects: list[Path] | None,
    location_scope: Path | None,
) -> ResolveResult:
    ref_lower = ref.lower()
    candidates: list[tuple[str, Path]] = []
    seen: set[Path] = set()

    def add(source: str, path: Path) -> None:
        resolved = path.expanduser().resolve()
        if resolved in seen or not is_project_directory(resolved):
            return
        if resolved.name.lower() != ref_lower:
            return
        seen.add(resolved)
        candidates.append((source, resolved))

    search_roots = [cwd.parent]
    if location_scope is not None:
        search_roots.insert(0, location_scope.expanduser().resolve())

    for root in search_roots:
        add("sibling", root / ref)

    add("cwd", cwd / ref)

    for project in discover_nearby_projects(cwd):
        add("nearby", project)

    if session:
        for recent in session.recent_repositories:
            if recent.name.lower() == ref_lower:
                add("recent", recent)

    if workspace_projects:
        for project in workspace_projects:
            if project.name.lower() == ref_lower:
                add("workspace", project)

    if len(candidates) == 1:
        source, path = candidates[0]
        _log_resolution_match(ref, source, path)
        return ResolveResult(status=ResolveStatus.RESOLVED, path=path, ref=ref)
    if len(candidates) > 1:
        unique_paths = list(dict.fromkeys(path for _, path in candidates))
        if len(unique_paths) == 1:
            _log_resolution_match(ref, candidates[0][0], unique_paths[0])
            return ResolveResult(status=ResolveStatus.RESOLVED, path=unique_paths[0], ref=ref)
        return ResolveResult(
            status=ResolveStatus.AMBIGUOUS,
            candidates=unique_paths,
            ref=ref,
        )

    name_candidates = _collect_name_candidates(
        cwd=cwd,
        session=session,
        workspace_projects=workspace_projects,
    )
    suggestions = _similar_names(ref, name_candidates)
    return ResolveResult(status=ResolveStatus.NOT_FOUND, ref=ref, suggestions=suggestions)


def resolve_repository_reference(
    ref: str,
    *,
    cwd: Path,
    session: AssistantSession | None = None,
    workspace_projects: list[Path] | None = None,
    location_scope: Path | None = None,
) -> ResolveResult:
    ref = ref.strip().strip('"').strip("'")
    if not ref:
        return ResolveResult(status=ResolveStatus.NOT_FOUND, ref=ref)

    cwd = cwd.expanduser().resolve()
    candidate = Path(ref).expanduser()
    if ref.startswith("~") or candidate.is_absolute():
        resolved = candidate.resolve()
        if is_project_directory(resolved):
            _log_resolution_match(ref, "absolute", resolved)
            return ResolveResult(status=ResolveStatus.RESOLVED, path=resolved, ref=ref)
        return ResolveResult(status=ResolveStatus.NOT_FOUND, ref=ref)

    if ref.startswith("./") or ref.startswith("../"):
        resolved = (cwd / ref).resolve()
        if is_project_directory(resolved):
            _log_resolution_match(ref, "relative", resolved)
            return ResolveResult(status=ResolveStatus.RESOLVED, path=resolved, ref=ref)
        return ResolveResult(status=ResolveStatus.NOT_FOUND, ref=ref)

    return _resolve_bare_name(
        ref,
        cwd=cwd,
        session=session,
        workspace_projects=workspace_projects,
        location_scope=location_scope,
    )


def resolve_references(
    refs: list[str],
    *,
    cwd: Path,
    session: AssistantSession | None = None,
    workspace_projects: list[Path] | None = None,
    location_scope: Path | None = None,
) -> dict[str, ResolveResult]:
    return {
        ref: resolve_repository_reference(
            ref,
            cwd=cwd,
            session=session,
            workspace_projects=workspace_projects,
            location_scope=location_scope,
        )
        for ref in refs
    }
