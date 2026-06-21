import hashlib
import logging
import re
import shutil
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from smith.core.exceptions import GitNotRepositoryError
from smith.models.workstation_health import (
    WORKSTATION_HEALTH_CACHE_FILE,
    ConsolidatedFinding,
    CorrelationInsight,
    RawFinding,
    Recommendation,
    WorkstationHealthCache,
    WorkstationHealthReport,
)
from smith.services.doctor import CheckResult, CheckStatus
from smith.services.git_intelligence import GitIntelligenceService
from smith.tools.fs_utils import format_bytes, should_skip_path

logger = logging.getLogger(__name__)

SAFETY_FOOTER = "Smith did not modify any files. Review recommendations before taking action."

CACHE_DIR_NAMES = {
    "node_modules",
    "__pycache__",
    ".cache",
    "dist",
    "target",
    ".venv",
    "venv",
}

PROJECT_MARKERS = {
    "pyproject.toml",
    "package.json",
    "build.gradle.kts",
    "pom.xml",
    "Cargo.toml",
    "requirements.txt",
}

SECTION_ORDER = ("System Resources", "File System Entropy", "Project Health", "Git Health")

CATEGORY_TO_SECTION = {
    "system": "System Resources",
    "entropy": "File System Entropy",
    "project": "Project Health",
}

_SEVERITY_RANK = {
    CheckStatus.CRITICAL: 0,
    CheckStatus.WARN: 1,
    CheckStatus.OK: 2,
}


def _display_path(path: Path) -> str:
    home = Path.home()
    try:
        return f"~/{path.relative_to(home)}"
    except ValueError:
        return str(path)


def resolve_scan_paths(paths: list[Path] | None, cwd: Path | None = None) -> list[Path]:
    if paths:
        resolved = [p.expanduser().resolve() for p in paths]
        return [p for p in resolved if p.exists()]

    candidates = [
        Path.home() / "Downloads",
        Path.home() / "Desktop",
        Path.home() / "Documents",
    ]
    base = (cwd or Path.cwd()).expanduser().resolve()
    if any((base / marker).is_file() for marker in PROJECT_MARKERS):
        candidates.append(base)

    seen: set[Path] = set()
    result: list[Path] = []
    for path in candidates:
        resolved = path.expanduser().resolve()
        if resolved.exists() and resolved not in seen:
            seen.add(resolved)
            result.append(resolved)
    return result


def _walk_files(
    roots: list[Path],
    *,
    max_depth: int,
    max_files: int,
) -> Iterator[Path]:
    count = 0
    for root in roots:
        for path in root.rglob("*"):
            if not path.is_file() or should_skip_path(path, root):
                continue
            try:
                rel_depth = len(path.relative_to(root).parts)
            except ValueError:
                continue
            if rel_depth > max_depth:
                continue
            yield path
            count += 1
            if count >= max_files:
                return


def _dir_size(path: Path, *, max_depth: int = 6) -> int:
    total = 0
    try:
        for item in path.rglob("*"):
            if item.is_file():
                try:
                    rel = item.relative_to(path)
                except ValueError:
                    continue
                if len(rel.parts) > max_depth:
                    continue
                try:
                    total += item.stat().st_size
                except OSError:
                    continue
    except OSError:
        pass
    return total


def _quick_hash(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with path.open("rb") as f:
            h.update(f.read(1024))
    except OSError:
        return ""
    return h.hexdigest()


def _max_severity(a: CheckStatus, b: CheckStatus) -> CheckStatus:
    return a if _SEVERITY_RANK[a] <= _SEVERITY_RANK[b] else b


def scan_disk() -> list[RawFinding]:
    usage = shutil.disk_usage(Path.home())
    free_pct = (usage.free / usage.total) * 100 if usage.total else 100.0
    severity = CheckStatus.OK
    if free_pct < 5:
        severity = CheckStatus.CRITICAL
    elif free_pct < 10:
        severity = CheckStatus.WARN
    elif free_pct < 20:
        severity = CheckStatus.WARN

    free_label = format_bytes(usage.free)
    total_label = format_bytes(usage.total)
    summary = f"Disk free: {free_pct:.1f}% ({free_label} of {total_label})"
    if severity == CheckStatus.OK:
        return []

    return [
        RawFinding(
            scanner="disk",
            category="system",
            severity=severity,
            key="disk:home",
            summary=summary,
            detail_lines=[
                f"Free: {format_bytes(usage.free)}",
                f"Used: {format_bytes(usage.used)}",
                f"Total: {format_bytes(usage.total)}",
            ],
            metrics={"free_pct": free_pct, "free_bytes": usage.free, "total_bytes": usage.total},
        )
    ]


def scan_clutter(path: Path) -> list[RawFinding]:
    if not path.is_dir():
        return []
    loose = [p for p in path.iterdir() if p.is_file() and not p.name.startswith(".")]
    if not loose:
        return []

    count = len(loose)
    severity = CheckStatus.WARN if count > 50 else CheckStatus.OK
    if severity == CheckStatus.OK:
        return []

    return [
        RawFinding(
            scanner="clutter",
            category="entropy",
            severity=severity,
            key=f"clutter:{path}",
            summary=f"{count} loose files in {_display_path(path)}",
            detail_lines=[f"Loose files: {count}"],
            metrics={"path": str(path), "loose_count": count},
        )
    ]


def scan_stale(path: Path, *, stale_days: int) -> list[RawFinding]:
    if not path.is_dir():
        return []
    import time

    cutoff = time.time() - (stale_days * 86400)
    stale_count = 0
    total_files = 0
    for file_path in _walk_files([path], max_depth=2, max_files=2000):
        total_files += 1
        try:
            if file_path.stat().st_mtime < cutoff:
                stale_count += 1
        except OSError:
            continue

    if stale_count == 0:
        return []

    ratio = stale_count / total_files if total_files else 0.0
    severity = CheckStatus.WARN if stale_count > 20 or ratio > 0.4 else CheckStatus.OK
    if severity == CheckStatus.OK and stale_count > 5:
        severity = CheckStatus.WARN
    if stale_count <= 0:
        return []

    return [
        RawFinding(
            scanner="stale",
            category="entropy",
            severity=severity,
            key=f"stale:{path}",
            summary=f"{stale_count} stale files (>{stale_days}d) in {_display_path(path)}",
            detail_lines=[
                f"Stale files: {stale_count}",
                f"Total scanned: {total_files}",
                f"Stale ratio: {ratio:.0%}",
            ],
            metrics={
                "path": str(path),
                "stale_count": stale_count,
                "total_files": total_files,
                "stale_ratio": ratio,
            },
        )
    ]


def scan_cache(roots: list[Path], *, max_depth: int) -> list[RawFinding]:
    findings: list[RawFinding] = []
    for root in roots:
        cache_bytes = 0
        cache_dirs: list[tuple[str, int]] = []
        for dir_name in CACHE_DIR_NAMES:
            for cache_path in root.rglob(dir_name):
                if not cache_path.is_dir():
                    continue
                try:
                    if len(cache_path.relative_to(root).parts) > max_depth:
                        continue
                except ValueError:
                    continue
                size = _dir_size(cache_path)
                if size > 0:
                    cache_bytes += size
                    cache_dirs.append((str(cache_path.relative_to(root)), size))

        if cache_bytes < 100 * 1024 * 1024:
            continue

        severity = CheckStatus.WARN if cache_bytes > 1024**3 else CheckStatus.WARN
        node_modules_bytes = sum(size for name, size in cache_dirs if "node_modules" in name)
        lines = [f"Total cache: {format_bytes(cache_bytes)}"]
        for name, size in sorted(cache_dirs, key=lambda x: -x[1])[:5]:
            lines.append(f"  {name}: {format_bytes(size)}")

        findings.append(
            RawFinding(
                scanner="cache",
                category="system",
                severity=severity,
                key=f"cache:{root}",
                summary=f"Cache buildup {format_bytes(cache_bytes)} in {_display_path(root)}",
                detail_lines=lines,
                metrics={
                    "path": str(root),
                    "cache_bytes": cache_bytes,
                    "node_modules_bytes": node_modules_bytes,
                    "cache_dirs": cache_dirs,
                },
            )
        )
    return findings


def scan_large_files(
    roots: list[Path],
    *,
    min_size_mb: int,
    max_depth: int,
    max_files: int,
) -> list[RawFinding]:
    threshold = min_size_mb * 1024 * 1024
    large: list[tuple[Path, int, Path]] = []
    for file_path in _walk_files(roots, max_depth=max_depth, max_files=max_files):
        try:
            size = file_path.stat().st_size
        except OSError:
            continue
        if size >= threshold:
            root = next(r for r in roots if str(file_path).startswith(str(r)))
            large.append((file_path, size, root))

    if not large:
        return []

    large.sort(key=lambda x: -x[1])
    top = large[:10]
    by_root: dict[Path, list[tuple[Path, int]]] = defaultdict(list)
    for file_path, size, root in top:
        by_root[root].append((file_path, size))

    findings: list[RawFinding] = []
    for root, items in by_root.items():
        lines = [f"{p.relative_to(root)}: {format_bytes(s)}" for p, s in items]
        findings.append(
            RawFinding(
                scanner="large_files",
                category="system",
                severity=CheckStatus.WARN,
                key=f"large_files:{root}",
                summary=f"{len(items)} large files (>={min_size_mb}MB) in {_display_path(root)}",
                detail_lines=lines,
                metrics={
                    "path": str(root),
                    "large_files": [(str(p), s) for p, s in items],
                    "largest_bytes": items[0][1] if items else 0,
                },
            )
        )
    return findings


def scan_logs(roots: list[Path], *, max_depth: int) -> list[RawFinding]:
    findings: list[RawFinding] = []
    for root in roots:
        log_files: list[tuple[Path, int]] = []
        for file_path in _walk_files(roots=[root], max_depth=max_depth, max_files=3000):
            if file_path.suffix.lower() != ".log":
                continue
            if any(part in CACHE_DIR_NAMES for part in file_path.parts):
                continue
            try:
                size = file_path.stat().st_size
            except OSError:
                continue
            log_files.append((file_path, size))

        big_logs = [(p, s) for p, s in log_files if s > 10 * 1024 * 1024]
        if len(log_files) <= 20 and not big_logs:
            continue

        severity = CheckStatus.WARN if big_logs or len(log_files) > 20 else CheckStatus.OK
        if severity == CheckStatus.OK:
            continue

        findings.append(
            RawFinding(
                scanner="logs",
                category="entropy",
                severity=severity,
                key=f"logs:{root}",
                summary=f"Log accumulation in {_display_path(root)} ({len(log_files)} files)",
                detail_lines=[f"Log files: {len(log_files)}", f"Large logs: {len(big_logs)}"],
                metrics={
                    "path": str(root),
                    "log_count": len(log_files),
                    "big_log_count": len(big_logs),
                },
            )
        )
    return findings


def scan_naming(roots: list[Path]) -> list[RawFinding]:
    findings: list[RawFinding] = []
    for root in roots:
        if not root.is_dir():
            continue
        dirs = [p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")]
        if len(dirs) < 3:
            continue

        has_space = any(" " in d.name for d in dirs)
        has_dash = any("-" in d.name for d in dirs)
        has_underscore = any("_" in d.name for d in dirs)
        mixed = sum([has_space, has_dash, has_underscore]) >= 2

        junk_count = sum(
            1 for p in root.rglob("*") if p.is_file() and p.name in (".DS_Store", "Thumbs.db")
        )

        if not mixed and junk_count <= 3:
            continue

        severity = CheckStatus.WARN if mixed else CheckStatus.OK
        if junk_count > 3:
            severity = CheckStatus.WARN

        findings.append(
            RawFinding(
                scanner="naming",
                category="entropy",
                severity=severity,
                key=f"naming:{root}",
                summary=f"Naming inconsistencies in {_display_path(root)}",
                detail_lines=[
                    f"Mixed naming conventions: {mixed}",
                    f"Junk metadata files: {junk_count}",
                ],
                metrics={"path": str(root), "mixed_naming": mixed, "junk_count": junk_count},
            )
        )
    return findings


def scan_duplicates_hint(path: Path, *, max_files: int = 500) -> list[RawFinding]:
    if not path.is_dir():
        return []

    by_size: dict[int, list[Path]] = defaultdict(list)
    count = 0
    for file_path in path.rglob("*"):
        if not file_path.is_file() or should_skip_path(file_path, path):
            continue
        try:
            size = file_path.stat().st_size
        except OSError:
            continue
        if size == 0:
            continue
        by_size[size].append(file_path)
        count += 1
        if count >= max_files:
            break

    groups = 0
    recoverable = 0
    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        buckets: dict[str, list[Path]] = defaultdict(list)
        for p in paths:
            buckets[_quick_hash(p)].append(p)
        for bucket in buckets.values():
            if len(bucket) > 1:
                groups += 1
                recoverable += size * (len(bucket) - 1)

    if groups == 0:
        return []

    return [
        RawFinding(
            scanner="duplicates",
            category="project",
            severity=CheckStatus.WARN,
            key=f"duplicates:{path}",
            summary=f"{groups} duplicate groups in {_display_path(path)}",
            detail_lines=[
                f"Recoverable: {format_bytes(recoverable)}",
                f"Groups: {groups}",
            ],
            metrics={
                "path": str(path),
                "duplicate_groups": groups,
                "recoverable_bytes": recoverable,
            },
        )
    ]


def _has_version_pin(line: str) -> bool:
    return bool(re.search(r"(==|>=|~=|<=|<|>)", line))


def scan_manifests(
    roots: list[Path], *, max_depth: int, max_projects: int = 20
) -> list[RawFinding]:
    findings: list[RawFinding] = []
    seen_projects: set[Path] = set()

    for root in roots:
        for marker in PROJECT_MARKERS:
            for manifest in root.rglob(marker):
                if should_skip_path(manifest, root):
                    continue
                try:
                    if len(manifest.relative_to(root).parts) > max_depth:
                        continue
                except ValueError:
                    continue
                project_root = manifest.parent
                if project_root in seen_projects:
                    continue
                seen_projects.add(project_root)
                if len(seen_projects) > max_projects:
                    break

                issues: list[str] = []
                if marker == "requirements.txt":
                    text = manifest.read_text(encoding="utf-8", errors="ignore")
                    unpinned = [
                        ln.strip()
                        for ln in text.splitlines()
                        if ln.strip() and not ln.startswith("#") and not _has_version_pin(ln)
                    ]
                    if unpinned:
                        issues.append(f"Unpinned deps: {', '.join(unpinned[:5])}")

                elif marker == "pyproject.toml":
                    text = manifest.read_text(encoding="utf-8", errors="ignore")
                    if "dependencies" in text.lower():
                        for line in text.splitlines():
                            stripped = line.strip().strip('",')
                            if stripped and not stripped.startswith("#") and stripped[0].isalpha():
                                if "dependencies" not in stripped and not _has_version_pin(
                                    stripped
                                ):
                                    if re.match(r"^[a-zA-Z0-9_-]+$", stripped.split("[")[0]):
                                        issues.append(f"Possibly unpinned: {stripped}")

                elif marker == "package.json":
                    text = manifest.read_text(encoding="utf-8", errors="ignore")
                    if "@nestjs" not in text and '"dependencies"' in text:
                        if "*" in text or "latest" in text.lower():
                            issues.append("Unpinned or wildcard dependencies")
                    lock_files = ("package-lock.json", "pnpm-lock.yaml", "yarn.lock")
                    if not any((project_root / lf).is_file() for lf in lock_files):
                        issues.append("Missing lock file")

                if not (project_root / ".gitignore").is_file():
                    issues.append("Missing .gitignore")
                if not any((project_root / d).exists() for d in ("tests", "test", "src/test")):
                    issues.append("No tests directory detected")

                if not issues:
                    continue

                parent = str(project_root.parent)
                findings.append(
                    RawFinding(
                        scanner="manifest",
                        category="project",
                        severity=CheckStatus.WARN,
                        key=f"manifest:{project_root}",
                        summary=f"Manifest issues in {_display_path(project_root)}",
                        detail_lines=issues[:6],
                        metrics={
                            "path": str(project_root),
                            "parent": parent,
                            "project_name": project_root.name,
                            "issues": issues,
                            "unpinned_count": len(
                                [i for i in issues if "unpinned" in i.lower() or "Unpinned" in i]
                            ),
                        },
                    )
                )

    return findings


def run_all_scanners(
    paths: list[Path],
    *,
    stale_days: int,
    min_size_mb: int,
    max_depth: int,
    max_files: int,
) -> list[RawFinding]:
    findings: list[RawFinding] = []
    findings.extend(scan_disk())
    for path in paths:
        findings.extend(scan_clutter(path))
        findings.extend(scan_stale(path, stale_days=stale_days))
        findings.extend(scan_duplicates_hint(path))
    findings.extend(scan_cache(paths, max_depth=max_depth))
    findings.extend(
        scan_large_files(paths, min_size_mb=min_size_mb, max_depth=max_depth, max_files=max_files)
    )
    findings.extend(scan_logs(paths, max_depth=max_depth))
    findings.extend(scan_naming(paths))
    findings.extend(scan_manifests(paths, max_depth=max_depth))
    return findings


def normalize_findings(raw: list[RawFinding]) -> list[ConsolidatedFinding]:
    by_key: dict[str, RawFinding] = {}
    for finding in raw:
        existing = by_key.get(finding.key)
        if existing is None or _SEVERITY_RANK[finding.severity] < _SEVERITY_RANK[existing.severity]:
            by_key[finding.key] = finding

    remaining = list(by_key.values())
    consolidated: list[ConsolidatedFinding] = []
    absorbed_keys: set[str] = set()

    cache_findings = [f for f in remaining if f.scanner == "cache"]
    large_findings = [f for f in remaining if f.scanner == "large_files"]

    for cache in cache_findings:
        cache_path = cache.metrics.get("path", "")
        node_modules_bytes = cache.metrics.get("node_modules_bytes", 0)
        cache_bytes = cache.metrics.get("cache_bytes", 1)
        related = ["cache"]

        for large in large_findings:
            if large.metrics.get("path") == cache_path:
                if node_modules_bytes >= 0.6 * cache_bytes:
                    absorbed_keys.add(large.key)
                    related.append("large_files")

        consolidated.append(
            ConsolidatedFinding(
                key=cache.key,
                category="system",
                primary_scanner="cache",
                severity=cache.severity,
                summary=cache.summary,
                detail_lines=cache.detail_lines,
                related_scanners=related,
                metrics=dict(cache.metrics),
            )
        )

    entropy_by_path: dict[str, list[RawFinding]] = defaultdict(list)
    for finding in remaining:
        if finding.scanner in ("clutter", "stale") and finding.key not in absorbed_keys:
            path = finding.metrics.get("path", finding.key)
            entropy_by_path[str(path)].append(finding)

    for path, group in entropy_by_path.items():
        clutter = next((f for f in group if f.scanner == "clutter"), None)
        stale = next((f for f in group if f.scanner == "stale"), None)
        scanners = [f.scanner for f in group]
        severity = CheckStatus.OK
        metrics: dict[str, Any] = {"path": path}
        detail_lines: list[str] = []

        for f in group:
            severity = _max_severity(severity, f.severity)
            detail_lines.extend(f.detail_lines)

        if clutter:
            metrics["loose_count"] = clutter.metrics.get("loose_count", 0)
        if stale:
            metrics["stale_count"] = stale.metrics.get("stale_count", 0)
            metrics["stale_ratio"] = stale.metrics.get("stale_ratio", 0.0)

        loose = metrics.get("loose_count", 0)
        stale_count = metrics.get("stale_count", 0)
        if clutter and stale:
            summary = (
                f"Workspace entropy in {_display_path(Path(path))}: "
                f"{loose} loose, {stale_count} stale files"
            )
            key = f"entropy:{path}"
            for f in group:
                absorbed_keys.add(f.key)
        elif clutter:
            summary = clutter.summary
            key = clutter.key
            absorbed_keys.add(clutter.key)
        elif stale:
            summary = stale.summary
            key = stale.key
            absorbed_keys.add(stale.key)
        else:
            continue

        consolidated.append(
            ConsolidatedFinding(
                key=key,
                category="entropy",
                primary_scanner="entropy" if len(scanners) > 1 else scanners[0],
                severity=severity,
                summary=summary,
                detail_lines=detail_lines,
                related_scanners=scanners,
                metrics=metrics,
            )
        )

    for finding in remaining:
        if finding.key in absorbed_keys:
            continue
        if finding.scanner in ("cache", "clutter", "stale"):
            continue
        if finding.scanner == "logs":
            path = finding.metrics.get("path", "")
            cache_at_path = any(
                c.metrics.get("path") == path for c in cache_findings if c.key not in absorbed_keys
            )
            if cache_at_path:
                continue

        consolidated.append(
            ConsolidatedFinding(
                key=finding.key,
                category=finding.category,
                primary_scanner=finding.scanner,
                severity=finding.severity,
                summary=finding.summary,
                detail_lines=finding.detail_lines,
                related_scanners=[finding.scanner],
                metrics=dict(finding.metrics),
            )
        )

    consolidated.sort(key=lambda f: (_SEVERITY_RANK[f.severity], f.summary))
    return consolidated


def correlate_findings(findings: list[ConsolidatedFinding]) -> list[CorrelationInsight]:
    insights: list[CorrelationInsight] = []

    disk = next((f for f in findings if f.primary_scanner == "disk"), None)
    cache = next((f for f in findings if f.primary_scanner == "cache"), None)
    if disk and cache:
        free_pct = disk.metrics.get("free_pct", 100)
        cache_bytes = cache.metrics.get("cache_bytes", 0)
        if free_pct < 10 and cache_bytes > 500 * 1024 * 1024:
            insights.append(
                CorrelationInsight(
                    related_keys=[disk.key, cache.key],
                    insight=(
                        "High cache usage combined with low disk space suggests "
                        "dependency artifacts are a primary driver."
                    ),
                )
            )

    for finding in findings:
        if finding.primary_scanner in ("entropy", "clutter", "stale"):
            ratio = finding.metrics.get("stale_ratio", 0.0)
            loose = finding.metrics.get("loose_count", 0)
            if ratio > 0.4 and loose > 30:
                insights.append(
                    CorrelationInsight(
                        related_keys=[finding.key],
                        insight=(
                            "Stale and loose files together indicate workspace entropy "
                            "rather than isolated old files."
                        ),
                    )
                )
                break

    dupes = [f for f in findings if f.primary_scanner == "duplicates"]
    naming = [f for f in findings if f.primary_scanner == "naming"]
    for dup in dupes:
        dup_path = dup.metrics.get("path", "")
        for name in naming:
            if name.metrics.get("path") == dup_path:
                insights.append(
                    CorrelationInsight(
                        related_keys=[dup.key, name.key],
                        insight=(
                            "Duplicate files alongside inconsistent naming may indicate "
                            "repeated manual copies."
                        ),
                    )
                )
                break

    manifests = [f for f in findings if f.primary_scanner == "manifest"]
    by_parent: dict[str, list[ConsolidatedFinding]] = defaultdict(list)
    for m in manifests:
        if m.metrics.get("unpinned_count", 0) > 0:
            by_parent[m.metrics.get("parent", "")].append(m)
    for _parent, group in by_parent.items():
        if len(group) >= 2:
            keys = [g.key for g in group]
            insights.append(
                CorrelationInsight(
                    related_keys=keys,
                    insight=(
                        "Multiple projects with unpinned dependencies increase "
                        "environment drift risk."
                    ),
                )
            )

    return insights


def category_penalty(base: float, count: int) -> float:
    return base * sum(0.5**i for i in range(min(count, 4)))


def compute_workstation_score_v2(
    findings: list[ConsolidatedFinding],
    correlations: list[CorrelationInsight],
) -> tuple[int, dict[str, int]]:
    breakdown: dict[str, int] = {}
    score = 100.0

    disk = next((f for f in findings if f.primary_scanner == "disk"), None)
    if disk:
        free_pct = disk.metrics.get("free_pct", 100)
        if free_pct < 5:
            penalty = 20
        elif free_pct < 10:
            penalty = 15
        elif free_pct < 20:
            penalty = 8
        else:
            penalty = 0
        if penalty:
            breakdown["disk"] = -penalty
            score -= penalty

    cache_findings = [f for f in findings if f.primary_scanner == "cache"]
    if cache_findings:
        total_cache = sum(f.metrics.get("cache_bytes", 0) for f in cache_findings)
        gb = total_cache / (1024**3)
        if gb >= 2:
            penalty = 15
        elif gb >= 1:
            penalty = 10
        elif gb >= 0.5:
            penalty = 5
        else:
            penalty = 0
        if penalty:
            breakdown["cache"] = -penalty
            score -= penalty

    entropy_findings = [
        f for f in findings if f.category == "entropy" and f.primary_scanner != "naming"
    ]
    if entropy_findings:
        base = 10.0
        penalty = int(category_penalty(base, len(entropy_findings)))
        if penalty:
            breakdown["entropy"] = -penalty
            score -= penalty

    naming_findings = [f for f in findings if f.primary_scanner == "naming"]
    if naming_findings:
        penalty = int(category_penalty(3.0, len(naming_findings)))
        if penalty:
            breakdown["naming"] = -min(penalty, 3)
            score -= breakdown["naming"]

    manifest_clusters: dict[str, int] = defaultdict(int)
    for f in findings:
        if f.primary_scanner == "manifest" and f.metrics.get("unpinned_count", 0) > 0:
            manifest_clusters[f.metrics.get("parent", f.key)] += 1
    if manifest_clusters:
        cluster_count = sum(1 for c in manifest_clusters.values() if c >= 1)
        penalty = min(int(category_penalty(4.0, cluster_count)), 12)
        if penalty:
            breakdown["manifest"] = -penalty
            score -= penalty

    dup_findings = [f for f in findings if f.primary_scanner == "duplicates"]
    if dup_findings:
        recoverable = sum(f.metrics.get("recoverable_bytes", 0) for f in dup_findings)
        if recoverable > 10 * 1024 * 1024:
            penalty = 8
        elif recoverable > 0:
            penalty = 4
        else:
            penalty = 0
        if penalty:
            breakdown["duplicates"] = -penalty
            score -= penalty

    large = [f for f in findings if f.primary_scanner == "large_files"]
    if large:
        penalty = int(category_penalty(6.0, len(large)))
        if penalty:
            breakdown["large_files"] = -min(penalty, 6)
            score -= breakdown["large_files"]

    if correlations and score > 0:
        pass

    final = max(0, min(100, int(round(score))))
    return final, breakdown


def _insight_for_keys(correlations: list[CorrelationInsight], keys: list[str]) -> str | None:
    key_set = set(keys)
    for insight in correlations:
        if key_set.intersection(insight.related_keys):
            return insight.insight
    return None


def build_recommendations_v2(
    findings: list[ConsolidatedFinding],
    correlations: list[CorrelationInsight],
    score_breakdown: dict[str, int],
) -> list[Recommendation]:
    recs: list[Recommendation] = []
    seen_intents: set[tuple[str, str]] = set()

    def add(rec: Recommendation) -> None:
        intent = (rec.category, rec.title.lower())
        if intent in seen_intents:
            return
        seen_intents.add(intent)
        recs.append(rec)

    disk = next((f for f in findings if f.primary_scanner == "disk"), None)
    cache = next((f for f in findings if f.primary_scanner == "cache"), None)
    if disk and cache and _insight_for_keys(correlations, [disk.key, cache.key]):
        insight = _insight_for_keys(correlations, [disk.key, cache.key])
        add(
            Recommendation(
                severity="warn",
                category="system",
                title="Review dependency caches before deleting personal files",
                detail="Low disk space with significant cache directories detected.",
                impact_reason="Free disk space affects build performance and IDE stability.",
                correlated_insight=insight,
                finding_keys=[disk.key, cache.key],
            )
        )
    elif disk:
        add(
            Recommendation(
                severity="warn",
                category="system",
                title="Free up disk space",
                detail=disk.summary,
                impact_reason="Free disk space affects build performance and IDE stability.",
                finding_keys=[disk.key],
            )
        )
    elif cache:
        add(
            Recommendation(
                severity="warn",
                category="system",
                title="Review cache directories",
                detail=cache.summary,
                impact_reason="Large caches consume disk space and slow backups.",
                finding_keys=[cache.key],
            )
        )

    for finding in findings:
        if finding.primary_scanner in ("entropy", "clutter", "stale"):
            path = finding.metrics.get("path", "")
            display = _display_path(Path(path)) if path else "workspace"
            insight = _insight_for_keys(correlations, [finding.key])
            loose = finding.metrics.get("loose_count", 0)
            cmd = f"smith organize {display} --dry-run" if loose > 30 else None
            add(
                Recommendation(
                    severity="warn" if finding.severity == CheckStatus.WARN else "info",
                    category="entropy",
                    title=f"Reduce workspace entropy in {display}",
                    detail=finding.summary,
                    impact_reason="Cluttered directories slow search and increase duplicate risk.",
                    suggested_command=cmd,
                    correlated_insight=insight,
                    finding_keys=[finding.key],
                )
            )
            break

    dup = next((f for f in findings if f.primary_scanner == "duplicates"), None)
    if dup:
        path = dup.metrics.get("path", "")
        display = _display_path(Path(path)) if path else "."
        recoverable = dup.metrics.get("recoverable_bytes", 0)
        insight = _insight_for_keys(correlations, [dup.key])
        cmd = f"smith duplicates {display}" if recoverable > 10 * 1024 * 1024 else None
        add(
            Recommendation(
                severity="warn",
                category="project",
                title=f"Review duplicate files in {display}",
                detail=dup.summary,
                impact_reason=f"Duplicates waste {format_bytes(recoverable)} of storage.",
                suggested_command=cmd,
                correlated_insight=insight,
                finding_keys=[dup.key],
            )
        )

    manifests = [f for f in findings if f.primary_scanner == "manifest"]
    unpinned = [m for m in manifests if m.metrics.get("unpinned_count", 0) > 0]
    if unpinned:
        names = ", ".join(m.metrics.get("project_name", "?") for m in unpinned[:5])
        keys = [m.key for m in unpinned]
        insight = _insight_for_keys(correlations, keys)
        add(
            Recommendation(
                severity="warn",
                category="project",
                title="Pin dependencies in project manifests",
                detail=f"Affected projects: {names}",
                impact_reason="Unpinned dependencies cause non-reproducible builds.",
                correlated_insight=insight,
                finding_keys=keys,
            )
        )

    naming = next((f for f in findings if f.primary_scanner == "naming"), None)
    if naming:
        add(
            Recommendation(
                severity="info",
                category="entropy",
                title="Standardize folder naming conventions",
                detail=naming.summary,
                impact_reason="Consistent naming improves navigation and automation.",
                finding_keys=[naming.key],
            )
        )

    if len(recs) > 8:
        recs = recs[:8]

    return recs


def align_score_and_recommendations(
    score: int,
    breakdown: dict[str, int],
    recommendations: list[Recommendation],
    findings: list[ConsolidatedFinding],
    correlations: list[CorrelationInsight],
) -> list[Recommendation]:
    recs = list(recommendations)
    covered: set[str] = set()
    for rec in recs:
        if rec.category == "system" and ("disk" in breakdown or "cache" in breakdown):
            covered.add("disk")
            covered.add("cache")
        if rec.category == "entropy":
            covered.add("entropy")
            covered.add("naming")
        if rec.category == "project":
            covered.add("manifest")
            covered.add("duplicates")

    category_labels = {
        "disk": ("system", "Address disk space pressure"),
        "cache": ("system", "Review cache accumulation"),
        "entropy": ("entropy", "Reduce workspace entropy"),
        "naming": ("entropy", "Review naming consistency"),
        "manifest": ("project", "Fix project manifest issues"),
        "duplicates": ("project", "Review duplicate files"),
        "large_files": ("system", "Review large files"),
    }

    for cat, penalty in breakdown.items():
        if abs(penalty) < 5:
            continue
        if cat in covered:
            continue
        insight_for_cat = any(
            insight
            for insight in correlations
            if any(
                f.primary_scanner == cat or f.category == category_labels.get(cat, ("", ""))[0]
                for f in findings
                if f.key in insight.related_keys
            )
        )
        if insight_for_cat:
            covered.add(cat)
            continue

        label_cat, title = category_labels.get(cat, ("system", f"Review {cat} findings"))
        logger.debug("Score deduction without recommendation: %s", cat)
        related = [f for f in findings if cat in f.primary_scanner or f.category == label_cat]
        detail = related[0].summary if related else f"Score impact: {penalty} points"
        recs.append(
            Recommendation(
                severity="warn",
                category=label_cat,
                title=title,
                detail=detail,
                impact_reason=f"This issue reduced your health score by {abs(penalty)} points.",
                finding_keys=[f.key for f in related[:3]],
            )
        )
        covered.add(cat)

    return recs[:8]


def _findings_to_sections(findings: list[ConsolidatedFinding]) -> list[tuple[str, CheckResult]]:
    grouped: dict[str, list[ConsolidatedFinding]] = {s: [] for s in SECTION_ORDER}
    for finding in findings:
        section = CATEGORY_TO_SECTION.get(finding.category, "Project Health")
        grouped[section].append(finding)

    sections: list[tuple[str, CheckResult]] = []
    for section_name in SECTION_ORDER:
        items = grouped[section_name]
        if not items:
            continue
        items.sort(key=lambda f: (_SEVERITY_RANK[f.severity], f.summary))
        worst = min(items, key=lambda f: _SEVERITY_RANK[f.severity])
        lines = []
        for item in items:
            lines.append(item.summary)
            lines.extend(f"  {ln}" for ln in item.detail_lines[:4])
        sections.append((section_name, CheckResult(status=worst.severity, lines=lines)))
    return sections


def _git_health_check(git_health) -> CheckResult:
    lines = [
        f"Branch: {git_health.branch}",
        f"Modified Files: {git_health.modified}",
        f"Untracked: {git_health.untracked}",
        f"Staged: {git_health.staged}",
        f"Status: {git_health.assessment.label}",
    ]
    return CheckResult(status=CheckStatus.OK, lines=lines)


def build_workstation_report(
    paths: list[Path] | None = None,
    *,
    stale_days: int = 90,
    min_size_mb: int = 50,
    max_depth: int = 4,
    max_files: int = 5000,
    cwd: Path | None = None,
) -> WorkstationHealthReport:
    scanned = resolve_scan_paths(paths, cwd=cwd)
    raw = run_all_scanners(
        scanned,
        stale_days=stale_days,
        min_size_mb=min_size_mb,
        max_depth=max_depth,
        max_files=max_files,
    )
    findings = normalize_findings(raw)
    correlations = correlate_findings(findings)
    score, breakdown = compute_workstation_score_v2(findings, correlations)
    recommendations = build_recommendations_v2(findings, correlations, breakdown)
    recommendations = align_score_and_recommendations(
        score, breakdown, recommendations, findings, correlations
    )
    issues = [f.summary for f in findings if f.severity != CheckStatus.OK]
    sections = _findings_to_sections(findings)

    try:
        git_health = GitIntelligenceService(cwd=cwd or Path.cwd()).get_git_health()
        sections.append(("Git Health", _git_health_check(git_health)))
    except GitNotRepositoryError:
        pass

    return WorkstationHealthReport(
        score=score,
        score_breakdown=breakdown,
        issues=issues,
        recommendations=recommendations,
        correlations=correlations,
        findings=findings,
        sections=sections,
        scanned_paths=[_display_path(p) for p in scanned],
    )


def report_to_markdown(report: WorkstationHealthReport) -> str:
    lines = [
        "# Workstation Health",
        "",
        f"Score: **{report.score}/100**",
        "",
    ]

    if report.correlations:
        lines.append("## Insights")
        for insight in report.correlations[:3]:
            lines.append(f"- {insight.insight}")
        lines.append("")

    for title, check in report.sections:
        lines.append(f"## {title}")
        for ln in check.lines:
            lines.append(f"- {ln}")
        lines.append("")

    if report.recommendations:
        lines.append("## Recommendations")
        for rec in report.recommendations:
            lines.append(f"### {rec.title}")
            lines.append(rec.detail)
            if rec.impact_reason:
                lines.append(f"*{rec.impact_reason}*")
            if rec.correlated_insight:
                lines.append(f"_{rec.correlated_insight}_")
            if rec.suggested_command:
                lines.append(f"`{rec.suggested_command}`")
            lines.append("")

    lines.append(f"_{SAFETY_FOOTER}_")
    lines.append("")
    lines.append(f"Scanned: {', '.join(report.scanned_paths) or 'none'}")
    return "\n".join(lines)


_STATUS_STYLE = {
    CheckStatus.OK: ("✓", "green"),
    CheckStatus.WARN: ("⚠", "yellow"),
    CheckStatus.CRITICAL: ("✗", "red"),
}


def render_workstation_health(report: WorkstationHealthReport, console) -> None:
    from rich.markup import escape
    from rich.panel import Panel
    from rich.table import Table

    console.print("[bold]Workstation Health[/bold]\n")

    summary_lines = [f"Score: {report.score}/100"]
    for insight in report.correlations[:3]:
        summary_lines.append(insight.insight)
    summary_lines.append(SAFETY_FOOTER)

    if report.score >= 80:
        style = "green"
    elif report.score >= 50:
        style = "yellow"
    else:
        style = "red"

    console.print(
        Panel(
            "\n".join(escape(ln) for ln in summary_lines),
            title="Summary",
            border_style=style,
            expand=False,
        )
    )
    console.print()

    for title, check in report.sections:
        table = Table(title=title, show_header=True, header_style="bold")
        table.add_column("Finding", style="dim")
        table.add_column("Status", width=8)
        icon, st = _STATUS_STYLE[check.status]
        for line in check.lines:
            if line.startswith("  "):
                table.add_row(line, "", "")
            else:
                table.add_row(line, f"[{st}]{icon}[/{st}]", "")
        console.print(table)
        console.print()

    if report.recommendations:
        rec_table = Table(title="Recommendations", show_header=True, header_style="bold")
        rec_table.add_column("Priority", width=8)
        rec_table.add_column("Recommendation")
        rec_table.add_column("Action")
        for rec in report.recommendations:
            detail = rec.detail
            if rec.impact_reason:
                detail += f"\n[dim]{rec.impact_reason}[/dim]"
            if rec.correlated_insight:
                detail += f"\n[dim italic]{rec.correlated_insight}[/dim italic]"
            action = rec.suggested_command or "—"
            rec_table.add_row(rec.severity.upper(), detail, action)
        console.print(rec_table)
        console.print()

    if report.scanned_paths:
        console.print(f"[dim]Scanned: {', '.join(report.scanned_paths)}[/dim]")


CONTEXT_DIR = ".smith"


def workstation_health_cache_path(cwd: Path) -> Path:
    return cwd.expanduser().resolve() / CONTEXT_DIR / WORKSTATION_HEALTH_CACHE_FILE


def save_workstation_health_cache(cwd: Path, report: WorkstationHealthReport) -> Path:
    from smith.services.gitignore import ensure_smith_gitignore_entry

    cache = WorkstationHealthCache.from_report(report)
    path = workstation_health_cache_path(cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cache.to_json(), encoding="utf-8")
    ensure_smith_gitignore_entry(cwd)
    return path


def load_workstation_health_cache(cwd: Path) -> WorkstationHealthCache | None:
    path = workstation_health_cache_path(cwd)
    if not path.is_file():
        return None
    try:
        return WorkstationHealthCache.from_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError, TypeError):
        return None
