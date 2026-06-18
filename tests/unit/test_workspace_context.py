import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from smith.models.project_context import ProjectContext
from smith.services.project_context import ProjectContextService, format_context_text


def _build(service: ProjectContextService, path: Path):
    context, _ = service.build(path)
    return context


@pytest.fixture
def drone_project(tmp_path: Path) -> Path:
    root = tmp_path / "drone-control"
    root.mkdir()
    (root / "build.gradle.kts").write_text(
        'plugins { id("org.springframework.boot") }\n'
        'dependencies { implementation("org.springframework.boot:spring-boot-starter") }'
    )
    (root / "Dockerfile").write_text("FROM eclipse-temurin:21\n")
    (root / "docker-compose.yml").write_text("services:\n  db:\n    image: postgres:16\n")
    workflows = root / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text("name: CI\n")

    for module in ("api", "domain", "infrastructure"):
        mod = root / module
        mod.mkdir()
        (mod / "build.gradle.kts").write_text('plugins { kotlin("jvm") }')

    api = root / "api" / "src" / "main" / "kotlin"
    api.mkdir(parents=True)
    (api / "Application.kt").write_text("@SpringBootApplication\nclass App\n")
    (root / "application.yml").write_text(
        "spring:\n  datasource:\n    url: jdbc:postgresql://localhost/drone\n"
    )
    return root


def test_kotlin_detection(drone_project: Path):
    service = ProjectContextService()
    context = _build(service, drone_project)
    assert context.language == "kotlin"


def test_spring_boot_detection(drone_project: Path):
    service = ProjectContextService()
    context = _build(service, drone_project)
    assert context.framework == "spring-boot"


def test_postgresql_detection(drone_project: Path):
    service = ProjectContextService()
    context = _build(service, drone_project)
    assert "postgresql" in context.database


def test_docker_detection(drone_project: Path):
    service = ProjectContextService()
    context = _build(service, drone_project)
    assert "docker" in context.infrastructure
    assert "docker-compose" in context.infrastructure


def test_github_actions_detection(drone_project: Path):
    service = ProjectContextService()
    context = _build(service, drone_project)
    assert "github-actions" in context.ci_cd


def test_module_discovery(drone_project: Path):
    service = ProjectContextService()
    context = _build(service, drone_project)
    assert set(context.modules) == {"api", "domain", "infrastructure"}


def test_save_and_load(drone_project: Path):
    service = ProjectContextService()
    built = _build(service, drone_project)
    service.save(drone_project, built)

    context_file = drone_project / ".smith" / "project_context.json"
    assert context_file.is_file()

    loaded = service.load(drone_project)
    assert loaded is not None
    assert loaded.project_name == "drone-control"
    assert loaded.language == "kotlin"
    assert loaded.framework == "spring-boot"


def test_refresh_overwrites(drone_project: Path):
    service = ProjectContextService()
    service.save(
        drone_project,
        ProjectContext(
            project_name="old",
            language="java",
            framework=None,
            build_system=None,
            database=[],
            infrastructure=[],
            ci_cd=[],
            modules=[],
            generated_at=datetime.now(UTC),
        ),
    )

    refreshed, _ = service.refresh(drone_project)
    assert refreshed.project_name == "drone-control"
    assert refreshed.language == "kotlin"

    stored = json.loads((drone_project / ".smith" / "project_context.json").read_text())
    assert stored["project_name"] == "drone-control"


def test_prompt_block_max_length(drone_project: Path):
    service = ProjectContextService()
    context = _build(service, drone_project)
    block = context.to_prompt_block(max_chars=500)
    assert len(block) <= 500
    assert "Current Project Context" in block
    assert "Kotlin" in block or "kotlin" in block.lower()


def test_format_context_text(drone_project: Path):
    service = ProjectContextService()
    context = _build(service, drone_project)
    text = format_context_text(context)
    assert "Project: drone-control" in text
    assert "Spring Boot" in text
    assert "PostgreSQL" in text


def test_json_roundtrip(drone_project: Path):
    service = ProjectContextService()
    original = _build(service, drone_project)
    restored = ProjectContext.from_json(original.to_json())
    assert restored.project_name == original.project_name
    assert restored.modules == original.modules
