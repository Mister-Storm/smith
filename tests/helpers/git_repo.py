import subprocess
from pathlib import Path

import pytest


def git_run(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def init_git_repo(tmp_path: Path, *, name: str = "repo") -> Path:
    repo = tmp_path / name
    repo.mkdir()
    git_run(repo, "init")
    git_run(repo, "config", "user.email", "test@example.com")
    git_run(repo, "config", "user.name", "Test User")
    (repo / "README.md").write_text("# test\n")
    git_run(repo, "add", "README.md")
    git_run(repo, "commit", "-m", "chore: initial commit")
    return repo


@pytest.fixture
def git_repo(tmp_path):
    return init_git_repo(tmp_path)
