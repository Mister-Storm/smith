import json
import os
import time
from pathlib import Path

from smith.models.workstation_health import RawFinding
from smith.services.doctor import CheckStatus
from smith.services.workstation_health import (
    align_score_and_recommendations,
    build_recommendations_v2,
    build_workstation_report,
    compute_workstation_score_v2,
    correlate_findings,
    normalize_findings,
    report_to_markdown,
    run_all_scanners,
)
from smith.tools.workstation_health import WorkstationHealthTool


def _cache_finding(path: str, cache_bytes: int, node_modules_bytes: int) -> RawFinding:
    return RawFinding(
        scanner="cache",
        category="system",
        severity=CheckStatus.WARN,
        key=f"cache:{path}",
        summary=f"Cache {cache_bytes}",
        metrics={
            "path": path,
            "cache_bytes": cache_bytes,
            "node_modules_bytes": node_modules_bytes,
            "cache_dirs": [("node_modules", node_modules_bytes)],
        },
    )


def _large_files_finding(path: str) -> RawFinding:
    return RawFinding(
        scanner="large_files",
        category="system",
        severity=CheckStatus.WARN,
        key=f"large_files:{path}",
        summary="Large node_modules file",
        metrics={"path": path, "large_files": [], "largest_bytes": 200 * 1024 * 1024},
    )


def test_cache_node_modules_not_double_reported():
    path = "/tmp/project"
    raw = [
        _cache_finding(path, cache_bytes=200_000_000, node_modules_bytes=150_000_000),
        _large_files_finding(path),
    ]
    consolidated = normalize_findings(raw)
    scanners = {f.primary_scanner for f in consolidated}
    assert "cache" in scanners
    assert "large_files" not in scanners
    assert len(consolidated) == 1


def test_clutter_stale_merged_entropy(tmp_path: Path):
    root = str(tmp_path / "downloads")
    os.makedirs(root)
    raw = [
        RawFinding(
            scanner="clutter",
            category="entropy",
            severity=CheckStatus.WARN,
            key=f"clutter:{root}",
            summary="clutter",
            metrics={"path": root, "loose_count": 55},
        ),
        RawFinding(
            scanner="stale",
            category="entropy",
            severity=CheckStatus.WARN,
            key=f"stale:{root}",
            summary="stale",
            metrics={"path": root, "stale_count": 40, "stale_ratio": 0.5},
        ),
    ]
    consolidated = normalize_findings(raw)
    entropy = [f for f in consolidated if f.primary_scanner in ("entropy", "clutter", "stale")]
    assert len(entropy) == 1
    assert entropy[0].metrics.get("loose_count") == 55
    assert entropy[0].metrics.get("stale_count") == 40


def test_correlate_disk_and_cache():
    from smith.models.workstation_health import ConsolidatedFinding

    disk = ConsolidatedFinding(
        key="disk:home",
        category="system",
        primary_scanner="disk",
        severity=CheckStatus.WARN,
        summary="Low disk",
        metrics={"free_pct": 8.0},
    )
    cache = ConsolidatedFinding(
        key="cache:/home/user",
        category="system",
        primary_scanner="cache",
        severity=CheckStatus.WARN,
        summary="Big cache",
        metrics={"cache_bytes": 600 * 1024 * 1024},
    )
    correlations = correlate_findings([disk, cache])
    assert any("dependency artifacts" in c.insight for c in correlations)

    score, breakdown = compute_workstation_score_v2([disk, cache], correlations)
    recs = build_recommendations_v2([disk, cache], correlations, breakdown)
    aligned = align_score_and_recommendations(score, breakdown, recs, [disk, cache], correlations)
    assert any(r.correlated_insight for r in aligned)


def test_scoring_diminishing_returns():
    from smith.models.workstation_health import ConsolidatedFinding

    naming_findings = [
        ConsolidatedFinding(
            key=f"naming:{i}",
            category="entropy",
            primary_scanner="naming",
            severity=CheckStatus.WARN,
            summary=f"Naming {i}",
            metrics={"path": f"/p/{i}"},
        )
        for i in range(5)
    ]
    score, breakdown = compute_workstation_score_v2(naming_findings, [])
    assert breakdown.get("naming", 0) >= -3
    assert score >= 97


def test_recommendations_deduplicated():
    from smith.models.workstation_health import ConsolidatedFinding

    finding = ConsolidatedFinding(
        key="entropy:/dl",
        category="entropy",
        primary_scanner="entropy",
        severity=CheckStatus.WARN,
        summary="entropy",
        metrics={"path": "/dl", "loose_count": 60},
    )
    score, breakdown = compute_workstation_score_v2([finding], [])
    recs = build_recommendations_v2([finding], [], breakdown)
    titles = [r.title for r in recs]
    assert len(titles) == len(set(titles))


def test_score_recommendation_alignment():
    from smith.models.workstation_health import ConsolidatedFinding

    disk = ConsolidatedFinding(
        key="disk:home",
        category="system",
        primary_scanner="disk",
        severity=CheckStatus.CRITICAL,
        summary="Critical disk",
        metrics={"free_pct": 3.0},
    )
    score, breakdown = compute_workstation_score_v2([disk], [])
    recs = build_recommendations_v2([disk], [], breakdown)
    aligned = align_score_and_recommendations(score, breakdown, recs, [disk], [])
    assert aligned
    major = {k for k, v in breakdown.items() if abs(v) >= 5}
    for cat in major:
        has_rec = any(cat in ("disk", "cache") and r.category == "system" for r in aligned) or any(
            r.impact_reason for r in aligned
        )
        assert has_rec


def test_deterministic_section_order(tmp_path: Path):
    root = tmp_path / "ws"
    root.mkdir()
    for i in range(55):
        (root / f"file_{i}.txt").write_text("x")

    report_a = build_workstation_report([root], max_depth=2, max_files=500)
    report_b = build_workstation_report([root], max_depth=2, max_files=500)
    order_a = [t for t, _ in report_a.sections]
    order_b = [t for t, _ in report_b.sections]
    assert order_a == order_b


def test_no_filesystem_mutations(tmp_path: Path):
    root = tmp_path / "downloads"
    root.mkdir()
    files = [root / f"f{i}.txt" for i in range(10)]
    for f in files:
        f.write_text("data")
    before = {str(f): (f.stat().st_mtime_ns, f.stat().st_size) for f in files}

    tool = WorkstationHealthTool()
    result = tool.execute(paths=[str(root)], max_depth=2, max_files=200)

    assert result.success
    for f in files:
        after = (f.stat().st_mtime_ns, f.stat().st_size)
        assert before[str(f)] == after


def test_stale_files_detected(tmp_path: Path):
    root = tmp_path / "old"
    root.mkdir()
    ancient = time.time() - (120 * 86400)
    for i in range(8):
        f = root / f"ancient_{i}.txt"
        f.write_text("old")
        os.utime(f, (ancient, ancient))

    report = build_workstation_report([root], stale_days=90, max_depth=2, max_files=500)
    assert any(f.primary_scanner in ("entropy", "stale") for f in report.findings)


def test_unpinned_deps_manifest(tmp_path: Path):
    proj = tmp_path / "app"
    proj.mkdir()
    (proj / "requirements.txt").write_text("requests\nflask\n")
    (proj / "main.py").write_text("print('hi')\n")

    report = build_workstation_report([proj], max_depth=3, max_files=500)
    manifest_findings = [f for f in report.findings if f.primary_scanner == "manifest"]
    assert manifest_findings


def test_json_export_shape(tmp_path: Path):
    root = tmp_path / "data"
    root.mkdir()
    (root / "a.txt").write_text("hello")

    tool = WorkstationHealthTool()
    result = tool.execute(paths=[str(root)], as_json=True, max_depth=2, max_files=100)
    payload = json.loads(result.message)
    assert "score" in payload
    assert "score_breakdown" in payload
    assert "recommendations" in payload
    assert "scanned_paths" in payload


def test_clutter_scan_via_runner(tmp_path: Path):
    root = tmp_path / "clutter"
    root.mkdir()
    for i in range(60):
        (root / f"item_{i}.pdf").write_text("x")

    findings = run_all_scanners([root], stale_days=90, min_size_mb=50, max_depth=2, max_files=500)
    clutter = [f for f in findings if f.scanner == "clutter"]
    assert clutter
    consolidated = normalize_findings(clutter)
    assert consolidated[0].category == "entropy"


def test_report_markdown_contains_safety_footer(tmp_path: Path):
    root = tmp_path / "x"
    root.mkdir()
    report = build_workstation_report([root], max_depth=1, max_files=50)
    md = report_to_markdown(report)
    assert "did not modify any files" in md.lower()


def test_resolve_scan_paths_explicit(tmp_path: Path):
    from smith.services.workstation_health import resolve_scan_paths

    root = tmp_path / "custom"
    root.mkdir()
    paths = resolve_scan_paths([root])
    assert paths == [root.resolve()]


def test_correlate_duplicates_and_naming():
    from smith.models.workstation_health import ConsolidatedFinding

    path = "/home/user/Downloads"
    dup = ConsolidatedFinding(
        key=f"duplicates:{path}",
        category="project",
        primary_scanner="duplicates",
        severity=CheckStatus.WARN,
        summary="dupes",
        metrics={"path": path, "duplicate_groups": 2, "recoverable_bytes": 20_000_000},
    )
    naming = ConsolidatedFinding(
        key=f"naming:{path}",
        category="entropy",
        primary_scanner="naming",
        severity=CheckStatus.WARN,
        summary="naming",
        metrics={"path": path, "mixed_naming": True},
    )
    insights = correlate_findings([dup, naming])
    assert any("Duplicate files" in i.insight for i in insights)


def test_report_from_dict_roundtrip(tmp_path: Path):
    from smith.models.workstation_health import WorkstationHealthReport

    root = tmp_path / "dl"
    root.mkdir()
    for i in range(55):
        (root / f"x{i}.txt").write_text("a")
    original = build_workstation_report([root], max_depth=2, max_files=300)
    restored = WorkstationHealthReport.from_dict(original.to_dict())
    assert restored.score == original.score
    assert len(restored.findings) == len(original.findings)


def test_render_workstation_health_smoke(tmp_path: Path):
    from io import StringIO

    from rich.console import Console

    from smith.services.workstation_health import render_workstation_health

    root = tmp_path / "ws"
    root.mkdir()
    for i in range(60):
        (root / f"f{i}.bin").write_text("data")
    report = build_workstation_report([root], max_depth=2, max_files=500)
    buffer = StringIO()
    console = Console(file=buffer, width=120, force_terminal=True)
    render_workstation_health(report, console)
    output = buffer.getvalue()
    assert "Workstation Health" in output
    assert str(report.score) in output


def test_disk_scan_low_space(monkeypatch):
    from smith.services.workstation_health import scan_disk

    class Usage:
        total = 1000
        used = 950
        free = 50

    monkeypatch.setattr("smith.services.workstation_health.shutil.disk_usage", lambda _: Usage())
    findings = scan_disk()
    assert findings
    assert findings[0].metrics["free_pct"] == 5.0


def test_cache_scan_finds_node_modules(tmp_path: Path):
    from smith.services.workstation_health import scan_cache

    nm = tmp_path / "proj" / "node_modules" / "pkg"
    nm.mkdir(parents=True)
    (nm / "index.js").write_bytes(b"x" * (120 * 1024 * 1024))
    findings = scan_cache([tmp_path], max_depth=6)
    assert findings
    assert findings[0].metrics["cache_bytes"] > 100 * 1024 * 1024


def test_align_injects_fallback_recommendation():
    from smith.models.workstation_health import ConsolidatedFinding

    large = ConsolidatedFinding(
        key="large_files:/x",
        category="system",
        primary_scanner="large_files",
        severity=CheckStatus.WARN,
        summary="Large files present",
        metrics={"path": "/x", "largest_bytes": 100_000_000},
    )
    score, breakdown = compute_workstation_score_v2([large], [])
    recs = build_recommendations_v2([large], [], breakdown)
    aligned = align_score_and_recommendations(score, breakdown, recs, [large], [])
    assert any("large" in r.title.lower() or "Review" in r.title for r in aligned)


def test_build_workstation_report_includes_git_health(tmp_path):
    from tests.helpers.git_repo import init_git_repo

    repo = init_git_repo(tmp_path)
    (repo / "changes.py").write_text("x = 1\n")
    report = build_workstation_report([repo], cwd=repo, max_depth=2, max_files=500)
    titles = [title for title, _ in report.sections]
    assert "Git Health" in titles
    git_section = next(check for title, check in report.sections if title == "Git Health")
    assert any("Branch:" in line for line in git_section.lines)
    assert any("Status:" in line for line in git_section.lines)


def test_build_workstation_report_skips_git_when_not_repo(tmp_path):
    root = tmp_path / "not-a-repo"
    root.mkdir()
    (root / "file.txt").write_text("data\n")
    report = build_workstation_report([root], cwd=root, max_depth=2, max_files=500)
    titles = [title for title, _ in report.sections]
    assert "Git Health" not in titles
