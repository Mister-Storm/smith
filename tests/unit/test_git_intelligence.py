import subprocess
from pathlib import Path

import pytest

from smith.core.exceptions import GitNotRepositoryError
from smith.models.git_intelligence import ChangeSummary, DevelopmentAssessment
from smith.services.git_intelligence import (
    GitIntelligenceService,
    _bucket_release_notes,
    _classify_area,
    _compute_assessment,
    _filter_smith_paths,
    _is_smith_internal,
    _parse_porcelain,
)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "README.md").write_text("# test\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "chore: initial commit")
    return repo


def test_non_repo_raises(tmp_path):
    with pytest.raises(GitNotRepositoryError, match="not a Git repository"):
        GitIntelligenceService(cwd=tmp_path)


def test_is_smith_internal():
    assert _is_smith_internal(".smith/project_context.json")
    assert _is_smith_internal(".smith/history/session.json")
    assert _is_smith_internal(".smith/cache/data.bin")
    assert _is_smith_internal(".smith/workspace_context.json")
    assert not _is_smith_internal("smith/services/git_intelligence.py")


def test_filter_smith_paths():
    paths = [
        "smith/services/git_intelligence.py",
        ".smith/project_context.json",
        ".smith/history/x.json",
    ]
    assert _filter_smith_paths(paths) == ["smith/services/git_intelligence.py"]


def test_classify_area_specialized():
    assert _classify_area("smith/services/git_intelligence.py") == "Git"
    assert _classify_area("smith/services/project_context.py") == "Context"
    assert _classify_area("smith/services/workstation_health.py") == "Health"
    assert _classify_area("smith/services/doctor.py") == "Services"
    assert _classify_area("tests/unit/test_git_intelligence.py") == "Tests"
    assert _classify_area(".github/workflows/ci.yml") == "CI/CD"


def test_compute_assessment():
    assert _compute_assessment(modified=0, untracked=0, staged=0) == DevelopmentAssessment.CLEAN
    assert (
        _compute_assessment(modified=1, untracked=0, staged=2)
        == DevelopmentAssessment.READY_FOR_COMMIT
    )
    assert (
        _compute_assessment(modified=5, untracked=0, staged=0)
        == DevelopmentAssessment.WORK_IN_PROGRESS
    )
    assert (
        _compute_assessment(modified=0, untracked=5, staged=0)
        == DevelopmentAssessment.WORK_IN_PROGRESS
    )


def test_parse_porcelain_ignores_smith():
    lines = [
        " M smith/services/git_intelligence.py",
        "?? .smith/project_context.json",
        "?? smith/models/git_intelligence.py",
    ]
    counts = _parse_porcelain(lines)
    assert counts["modified"] == 1
    assert counts["untracked"] == 1


def test_parse_porcelain_staged_and_untracked():
    lines = [
        "M  staged.py",
        " M modified.py",
        "?? new.py",
        "D  deleted.py",
    ]
    counts = _parse_porcelain(lines)
    assert counts["staged"] >= 1
    assert counts["modified"] >= 1
    assert counts["untracked"] == 1
    assert counts["deleted"] >= 1


def test_repository_status(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "smith" / "services").mkdir(parents=True)
    (repo / "smith" / "services" / "git_intelligence.py").write_text("# git\n")
    _git(repo, "checkout", "-b", "feat/git-intelligence")

    service = GitIntelligenceService(cwd=repo)
    status = service.get_repository_status()
    assert status.branch == "feat/git-intelligence"
    assert status.untracked >= 1 or status.modified >= 1
    assert status.assessment != DevelopmentAssessment.CLEAN


def test_smith_files_excluded_from_summary(tmp_path):
    repo = _init_repo(tmp_path)
    smith_dir = repo / ".smith"
    smith_dir.mkdir()
    (smith_dir / "project_context.json").write_text("{}")
    (repo / "real.py").write_text("x = 1")

    summary = GitIntelligenceService(cwd=repo).summarize_changes()
    assert ".smith/project_context.json" not in summary.files
    assert "real.py" in summary.files


def test_get_git_health(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "smith" / "services").mkdir(parents=True)
    (repo / "smith" / "services" / "git_intelligence.py").write_text("# git\n")
    _git(repo, "checkout", "-b", "feat/git")

    report = GitIntelligenceService(cwd=repo).get_git_health()
    assert report.repo_name == "repo"
    assert report.branch == "feat/git"
    assert report.recent_commits_7d >= 1
    assert report.largest_area == "Git"


def test_suggest_commit_messages_test_type(tmp_path):
    repo = _init_repo(tmp_path)
    test_file = repo / "tests" / "unit" / "test_git.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_x(): pass\n")

    suggestions = GitIntelligenceService(cwd=repo).suggest_commit_messages()
    assert suggestions[0].type == "test"


def test_suggest_commit_messages_feat_for_new_files(tmp_path):
    repo = _init_repo(tmp_path)
    new_file = repo / "smith" / "services" / "new_feature.py"
    new_file.parent.mkdir(parents=True)
    new_file.write_text("# new\n")

    suggestions = GitIntelligenceService(cwd=repo).suggest_commit_messages()
    assert suggestions[0].type == "feat"
    assert len(suggestions) <= 3


def test_release_note_buckets():
    subjects = [
        "feat: add git commands",
        "fix: resolve false positive",
        "refactor: simplify pipeline",
        "perf: speed up scan",
        "docs: update README",
        "test: add git tests",
        "chore: bump deps",
        "misc change without prefix",
    ]
    notes = _bucket_release_notes(subjects)
    assert notes.features == ["add git commands"]
    assert notes.fixes == ["resolve false positive"]
    assert notes.improvements == ["simplify pipeline", "speed up scan"]
    assert notes.documentation == ["update README"]
    assert notes.testing == ["add git tests"]
    assert notes.maintenance == ["bump deps"]
    assert notes.other == ["misc change without prefix"]


def test_change_summary_llm_summary_default():
    summary = ChangeSummary(files=["a.py"], areas=["Services"], summary_lines=["Updated services."])
    assert summary.llm_summary is None


def test_change_summary_llm_summary_optional():
    summary = ChangeSummary(
        files=["a.py"],
        areas=["Services"],
        summary_lines=["Updated services."],
        llm_summary="AI summary",
    )
    assert summary.llm_summary == "AI summary"
