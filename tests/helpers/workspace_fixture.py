from pathlib import Path

from tests.helpers.git_repo import git_run


def create_python_project(parent: Path, name: str, *, with_git: bool = True) -> Path:
    project = parent / name
    project.mkdir(parents=True)
    (project / "pyproject.toml").write_text("[project]\nname = '" + name + "'\n")
    (project / "README.md").write_text(f"# {name}\n")
    (project / "tests").mkdir(exist_ok=True)
    (project / "tests" / "test_app.py").write_text("def test_ok(): pass\n")
    (project / ".github" / "workflows").mkdir(parents=True)
    (project / ".github" / "workflows" / "ci.yml").write_text("name: ci\n")
    if with_git:
        git_run(project, "init")
        git_run(project, "config", "user.email", "test@example.com")
        git_run(project, "config", "user.name", "Test User")
        git_run(project, "add", ".")
        git_run(project, "commit", "-m", "chore: init")
    return project


def init_workspace(tmp_path: Path, *, project_count: int = 2) -> Path:
    workspace = tmp_path / "development"
    workspace.mkdir()
    for i in range(project_count):
        create_python_project(workspace, f"project-{i}")
    return workspace


def init_single_project_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "solo"
    workspace.mkdir()
    create_python_project(workspace, "only-app")
    return workspace
