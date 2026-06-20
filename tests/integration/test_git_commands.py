import subprocess
from pathlib import Path

from typer.testing import CliRunner

from smith.cli.app import app

runner = CliRunner()


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "project"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "README.md").write_text("# test\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "feat: initial commit")
    return repo


def test_git_summary_in_repo(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    (repo / "smith" / "services").mkdir(parents=True)
    (repo / "smith" / "services" / "git_intelligence.py").write_text("# git\n")
    _git(repo, "checkout", "-b", "feat/git-intelligence")
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["git", "summary"])
    assert result.exit_code == 0
    assert "Git Summary" in result.output
    assert "feat/git-intelligence" in result.output
    assert "Assessment" in result.output
    assert "Suggested Commit" in result.output


def test_git_health_in_repo(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    services = repo / "smith" / "services"
    services.mkdir(parents=True)
    (services / "workstation_health.py").write_text("# health\n")
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["git", "health"])
    assert result.exit_code == 0
    assert "Git Health" in result.output
    assert "Repository" in result.output
    assert "Recent Activity" in result.output
    assert "Assessment" in result.output


def test_git_changes_in_repo(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    (repo / "changes.py").write_text("x = 1\n")
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["git", "changes"])
    assert result.exit_code == 0
    assert "Git Changes" in result.output
    assert "changes.py" in result.output


def test_git_commit_message_in_repo(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    test_dir = repo / "tests"
    test_dir.mkdir()
    (test_dir / "test_a.py").write_text("def test_a(): pass\n")
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["git", "commit-message"])
    assert result.exit_code == 0
    assert "Suggested Commits" in result.output


def test_git_release_notes_in_repo(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    _git(repo, "commit", "--allow-empty", "-m", "docs: update readme")
    _git(repo, "commit", "--allow-empty", "-m", "fix: patch bug")
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["git", "release-notes", "--commits", "5"])
    assert result.exit_code == 0
    assert "Release Notes" in result.output
    assert "Features" in result.output or "Documentation" in result.output


def test_git_not_a_repository(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["git", "summary"])
    assert result.exit_code == 1
    assert "not a Git repository" in result.output


def test_health_includes_git_section(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    (repo / "file.txt").write_text("data\n")
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["health", "--paths", str(repo)])
    assert result.exit_code in (0, 1)
    assert "Git Health" in result.output
    assert "Assessment" in result.output or "Branch" in result.output
