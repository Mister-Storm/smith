from pathlib import Path

import pytest

from smith.services.context_detection import detect_project_context
from smith.services.project_context import ProjectContextService


@pytest.fixture
def spring_gradle_project(tmp_path: Path) -> Path:
    root = tmp_path / "spring-app"
    root.mkdir()
    (root / "build.gradle.kts").write_text(
        'plugins { id("org.springframework.boot") }\n'
        'dependencies { implementation("org.springframework.boot:spring-boot-starter") }'
    )
    src = root / "src" / "main" / "kotlin"
    src.mkdir(parents=True)
    (src / "Application.kt").write_text("@SpringBootApplication\nclass App\n")
    return root


@pytest.fixture
def fastapi_project(tmp_path: Path) -> Path:
    root = tmp_path / "fastapi-app"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "app"\ndependencies = ["fastapi>=0.100"]\n'
    )
    (root / "app.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n")
    return root


@pytest.fixture
def django_project(tmp_path: Path) -> Path:
    root = tmp_path / "django-app"
    root.mkdir()
    (root / "manage.py").write_text("#!/usr/bin/env python\n")
    (root / "requirements.txt").write_text("django>=4.0\n")
    return root


@pytest.fixture
def nestjs_project(tmp_path: Path) -> Path:
    root = tmp_path / "nest-app"
    root.mkdir()
    (root / "package.json").write_text(
        '{"name": "nest-app", "dependencies": {"@nestjs/core": "^10.0.0"}}\n'
    )
    return root


def test_false_positive_readme_spring_boot(tmp_path: Path):
    root = tmp_path / "python-app"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nname = "app"\n')
    (root / "main.py").write_text("print('hello')\n")
    (root / "README.md").write_text(
        "# Demo\n\nThis project uses Spring Boot and spring-boot-starter-web.\n"
    )

    detected, _ = detect_project_context(root)
    assert detected.language == "python"
    assert detected.framework is None


def test_false_positive_docs_postgresql(tmp_path: Path):
    root = tmp_path / "python-app"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nname = "app"\n')
    docs = root / "docs"
    docs.mkdir()
    (docs / "db.md").write_text("# Database\n\nWe use PostgreSQL for storage.\n")

    detected, _ = detect_project_context(root)
    assert detected.databases == []


def test_false_positive_markdown_docker(tmp_path: Path):
    root = tmp_path / "python-app"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nname = "app"\n')
    docs = root / "docs"
    docs.mkdir()
    (docs / "docker.md").write_text(
        "# Docker\n\n```dockerfile\nFROM python:3.12\n```\nAlso see docker-compose.yml examples.\n"
    )

    detected, _ = detect_project_context(root)
    assert detected.infrastructure == []


def test_false_positive_test_fixtures_spring_boot(tmp_path: Path):
    root = tmp_path / "smith-like"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nname = "app"\n')
    tests = root / "tests" / "unit"
    tests.mkdir(parents=True)
    (tests / "test_context.py").write_text(
        "GRADLE = 'dependencies { implementation(\"org.springframework.boot:spring-boot-starter\") }'\n"
        'ANNOTATION = "@SpringBootApplication\\n"\n'
    )

    service = ProjectContextService()
    context, _ = service.build(root)
    assert context.language == "python"
    assert context.framework is None


def test_positive_spring_boot_gradle(spring_gradle_project: Path):
    detected, _ = detect_project_context(spring_gradle_project)
    assert detected.framework == "spring-boot"
    assert "Spring Boot" in detected.frameworks


def test_positive_fastapi(fastapi_project: Path):
    detected, _ = detect_project_context(fastapi_project)
    assert detected.framework == "fastapi"


def test_positive_django(django_project: Path):
    detected, _ = detect_project_context(django_project)
    assert detected.framework == "django"


def test_positive_nestjs(nestjs_project: Path):
    detected, _ = detect_project_context(nestjs_project)
    assert detected.framework == "nestjs"


def test_build_system_hatch(tmp_path: Path):
    root = tmp_path / "hatch-app"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[build-system]\nrequires = ["hatchling"]\nbuild-backend = "hatchling.build"\n'
        '[tool.hatch.build.targets.wheel]\npackages = ["app"]\n'
        '[project]\nname = "app"\n'
    )

    detected, _ = detect_project_context(root)
    assert detected.build_system == "hatch"


def test_debug_trace_records_ignored(tmp_path: Path):
    root = tmp_path / "app"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nname = "app"\n')
    (root / "README.md").write_text("# App\n")

    _, trace = detect_project_context(root, debug=True)
    assert any("README" in p or "docs" in p for p in trace.ignored) or trace.ignored
