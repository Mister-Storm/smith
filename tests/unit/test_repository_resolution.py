from smith.models.assistant import AssistantSession, ResolveStatus
from smith.services.intent_detection import (
    extract_location_scope,
    extract_references,
    has_location_hint,
)
from smith.services.repository_resolution import (
    discover_nearby_projects,
    is_likely_repository_name_ref,
    is_project_directory,
    resolve_repository_reference,
)


def test_resolve_absolute_path(tmp_path):
    project = tmp_path / "BuildTwin"
    project.mkdir()
    (project / "pyproject.toml").write_text("[tool.poetry]\n", encoding="utf-8")
    result = resolve_repository_reference(str(project), cwd=tmp_path)
    assert result.status == ResolveStatus.RESOLVED
    assert result.path == project.resolve()


def test_resolve_sibling_bare_name(tmp_path):
    cwd = tmp_path / "smith"
    sibling = tmp_path / "BuildTwin"
    cwd.mkdir()
    sibling.mkdir()
    (sibling / "pyproject.toml").write_text("[tool.poetry]\n", encoding="utf-8")
    result = resolve_repository_reference("BuildTwin", cwd=cwd)
    assert result.status == ResolveStatus.RESOLVED
    assert result.path == sibling.resolve()


def test_resolve_sibling_settings_gradle_kts_only(tmp_path):
    cwd = tmp_path / "smith"
    sibling = tmp_path / "BuildTwin"
    cwd.mkdir()
    sibling.mkdir()
    (sibling / "settings.gradle.kts").write_text(
        'rootProject.name = "BuildTwin"\n', encoding="utf-8"
    )
    assert is_project_directory(sibling)
    result = resolve_repository_reference("BuildTwin", cwd=cwd)
    assert result.status == ResolveStatus.RESOLVED
    assert result.path == sibling.resolve()


def test_discover_nearby_projects_lists_siblings(tmp_path):
    cwd = tmp_path / "smith"
    sibling = tmp_path / "BuildTwin"
    cwd.mkdir()
    sibling.mkdir()
    (sibling / "build.gradle.kts").write_text("plugins {}\n", encoding="utf-8")
    nearby = discover_nearby_projects(cwd)
    assert sibling.resolve() in nearby


def test_resolve_tilde_path(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    project = home / "projects" / "BuildTwin"
    project.mkdir(parents=True)
    (project / "Cargo.toml").write_text("[package]\n", encoding="utf-8")
    ref = "~/projects/BuildTwin"
    result = resolve_repository_reference(ref, cwd=tmp_path / "smith")
    assert result.status == ResolveStatus.RESOLVED
    assert result.path == project.resolve()


def test_quoted_project_name(tmp_path):
    cwd = tmp_path / "smith"
    sibling = tmp_path / "BuildTwin"
    cwd.mkdir()
    sibling.mkdir()
    (sibling / "pyproject.toml").write_text("[tool.poetry]\n", encoding="utf-8")
    refs = extract_references('Analyze "BuildTwin" architecture')
    assert "BuildTwin" in refs
    result = resolve_repository_reference("BuildTwin", cwd=cwd)
    assert result.status == ResolveStatus.RESOLVED


def test_location_scope_parent(tmp_path):
    cwd = tmp_path / "smith"
    cwd.mkdir()
    scope = extract_location_scope("analyze project one directory above", cwd)
    assert scope == cwd.parent.resolve()
    assert has_location_hint("analyze project one directory above", cwd)


def test_resolve_relative_path(tmp_path):
    sibling = tmp_path / "BuildTwin"
    cwd = tmp_path / "app"
    cwd.mkdir()
    sibling.mkdir()
    (sibling / "Cargo.toml").write_text("[package]\n", encoding="utf-8")
    result = resolve_repository_reference("../BuildTwin", cwd=cwd)
    assert result.status == ResolveStatus.RESOLVED


def test_resolve_recent_repository(tmp_path):
    project = tmp_path / "BuildTwin"
    project.mkdir()
    (project / "pyproject.toml").write_text("[tool.poetry]\n", encoding="utf-8")
    session = AssistantSession(recent_repositories=[project.resolve()])
    cwd = tmp_path / "other"
    cwd.mkdir()
    result = resolve_repository_reference("BuildTwin", cwd=cwd, session=session)
    assert result.status == ResolveStatus.RESOLVED


def test_is_project_directory_with_git(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    assert is_project_directory(repo)


def test_levenshtein_suggests_typo(tmp_path):
    cwd = tmp_path / "smith"
    sibling = tmp_path / "BuildTwin"
    cwd.mkdir()
    sibling.mkdir()
    (sibling / "pyproject.toml").write_text("[tool.poetry]\n", encoding="utf-8")
    result = resolve_repository_reference("BuildTwing", cwd=cwd)
    assert result.status == ResolveStatus.NOT_FOUND
    assert "BuildTwin" in result.suggestions


def test_exact_match_not_suggested_as_typo(tmp_path):
    cwd = tmp_path / "smith"
    sibling = tmp_path / "BuildTwin"
    cwd.mkdir()
    sibling.mkdir()
    (sibling / "pyproject.toml").write_text("[tool.poetry]\n", encoding="utf-8")
    result = resolve_repository_reference("BuildTwin", cwd=cwd)
    assert result.status == ResolveStatus.RESOLVED


def test_not_found_lists_nearby_projects(tmp_path):
    from smith.services.repository_resolution import format_not_found_response

    cwd = tmp_path / "smith"
    sibling = tmp_path / "BuildTwin"
    cwd.mkdir()
    sibling.mkdir()
    (sibling / "pyproject.toml").write_text("[tool.poetry]\n", encoding="utf-8")
    nearby = discover_nearby_projects(cwd)
    text = format_not_found_response("Missing", [], nearby_projects=nearby)
    assert "Projects found nearby" in text
    assert "BuildTwin" in text


def test_resolve_sibling_lowercase_bare_name(tmp_path):
    cwd = tmp_path / "smith"
    sibling = tmp_path / "my-api"
    cwd.mkdir()
    sibling.mkdir()
    (sibling / "pyproject.toml").write_text("[tool.poetry]\n", encoding="utf-8")
    result = resolve_repository_reference("my-api", cwd=cwd)
    assert result.status == ResolveStatus.RESOLVED
    assert result.path == sibling.resolve()


def test_resolve_sibling_kebab_case(tmp_path):
    cwd = tmp_path / "smith"
    sibling = tmp_path / "build-twin"
    cwd.mkdir()
    sibling.mkdir()
    (sibling / "requirements.txt").write_text("django>=4.0\n", encoding="utf-8")
    assert is_project_directory(sibling)
    result = resolve_repository_reference("build-twin", cwd=cwd)
    assert result.status == ResolveStatus.RESOLVED
    assert result.path == sibling.resolve()


def test_is_likely_repository_name_ref_rejects_stop_words():
    assert not is_likely_repository_name_ref("analyze")
    assert not is_likely_repository_name_ref("project")
    assert not is_likely_repository_name_ref("analise")
    assert not is_likely_repository_name_ref("projeto")
    assert not is_likely_repository_name_ref("proponha")
    assert not is_likely_repository_name_ref("melhorias")
    assert is_likely_repository_name_ref("my-api")
    assert is_likely_repository_name_ref("frontend")
    assert is_likely_repository_name_ref("buildTwin-frontend")
