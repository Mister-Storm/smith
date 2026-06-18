import json
from pathlib import Path

import pytest

from smith.memory.project_contexts import ProjectContextStore
from smith.tools.analyze_project import AnalyzeProjectTool
from smith.tools.project_context import (
    ProjectContextTool,
    build_analysis_json,
    compute_health_score,
    context_to_markdown,
    generate_architecture_observations,
    generate_project_context,
)


@pytest.fixture
def spring_project(tmp_path: Path) -> Path:
    root = tmp_path / "demo"
    root.mkdir()
    (root / "build.gradle.kts").write_text(
        'plugins { id("org.springframework.boot") }\n'
        'dependencies { implementation("org.springframework.boot:spring-boot-starter") }'
    )
    (root / "Dockerfile").write_text("FROM eclipse-temurin:21\n")
    workflows = root / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text("name: CI\n")

    for module in ("api", "domain", "persistence"):
        mod = root / module
        mod.mkdir()
        (mod / "build.gradle.kts").write_text('plugins { kotlin("jvm") }')

    api = root / "api" / "src" / "main" / "kotlin" / "com" / "demo"
    api.mkdir(parents=True)
    (api / "Application.kt").write_text("@SpringBootApplication\nfun main() { }\n")
    (root / "application.yml").write_text(
        "spring:\n  datasource:\n    url: jdbc:postgresql://localhost/db\n"
    )

    test_dir = root / "api" / "src" / "test" / "kotlin"
    test_dir.mkdir(parents=True)
    (test_dir / "ApplicationTest.kt").write_text("class ApplicationTest {}\n")

    for layer in ("api", "service", "repository"):
        (root / layer).mkdir(exist_ok=True)

    return root


def test_generate_project_context_spring(spring_project: Path):
    context = generate_project_context(spring_project)

    assert context.language == "Kotlin"
    assert "Spring Boot" in context.frameworks
    assert context.build_system == "Gradle Kotlin DSL"
    assert "PostgreSQL" in context.databases
    assert "Docker" in context.containers
    assert "GitHub Actions" in context.ci_cd
    assert set(context.modules) == {"api", "domain", "persistence"}
    assert context.entry_points
    assert context.has_tests
    assert context.has_build_file
    assert "Layered Architecture" in context.detected_patterns


def test_health_score_high(spring_project: Path):
    context = generate_project_context(spring_project)
    score, issues = compute_health_score(context)

    assert score >= 80
    assert "missing tests" not in issues
    assert "no CI/CD detected" not in issues


def test_health_score_low(tmp_path: Path):
    proj = tmp_path / "bare"
    proj.mkdir()
    (proj / "Main.kt").write_text("fun main() {}\n")

    context = generate_project_context(proj)
    score, issues = compute_health_score(context)

    assert score < 70
    assert "missing tests" in issues
    assert "missing build files" in issues


def test_architecture_observations(spring_project: Path):
    context = generate_project_context(spring_project)
    text = generate_architecture_observations(context)

    assert "## Architecture Observations" in text
    assert "layered architecture" in text.lower()


def test_context_to_markdown(spring_project: Path):
    context = generate_project_context(spring_project)
    md = context_to_markdown(context)

    assert "# Project Context" in md
    assert "## Languages" in md
    assert "Kotlin" in md
    assert "## Frameworks" in md
    assert "Spring Boot" in md


def test_build_analysis_json(spring_project: Path):
    context = generate_project_context(spring_project)
    score, issues = compute_health_score(context)
    payload = build_analysis_json(context, score, issues)

    assert payload["health_score"] == score
    assert payload["language"] == "kotlin"
    assert "spring-boot" in payload["frameworks"]
    assert "api" in payload["modules"]
    assert isinstance(payload["issues"], list)


def test_project_context_tool(tmp_path: Path):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "build.gradle.kts").write_text('plugins { kotlin("jvm") }')
    (proj / "Main.kt").write_text("fun main() {}\n")

    tool = ProjectContextTool()
    result = tool.execute(path=str(proj), save=False)

    assert result.success
    assert "# Project Context" in result.message
    assert "## Project Health" in result.message
    assert result.metadata["health_score"] >= 0


def test_project_context_persistence(spring_project: Path, tmp_path: Path):
    db_path = tmp_path / "ctx.db"
    store = ProjectContextStore(db_path)

    context = generate_project_context(spring_project)
    store.save(context)

    assert store.count() == 1
    loaded = store.get_latest(spring_project)
    assert loaded is not None
    assert loaded.language == context.language
    assert loaded.modules == context.modules
    store.close()


def test_analyze_json_output(spring_project: Path):
    tool = AnalyzeProjectTool(None)
    result = tool.execute(path=str(spring_project), as_json=True)

    assert result.success
    payload = json.loads(result.message)
    assert "health_score" in payload
    assert payload["language"] == "kotlin"
    assert "spring-boot" in payload["frameworks"]


def test_analyze_structure_only(spring_project: Path):
    tool = AnalyzeProjectTool(None)
    result = tool.execute(path=str(spring_project), structure_only=True)

    assert result.success
    assert "# Project Context" in result.message
    assert "## Architecture Observations" in result.message
    assert "## Project Health" in result.message
    assert result.metadata["structure_only"] is True


def test_analyze_with_llm(spring_project: Path, fake_llm):
    fake_llm._response = "# Project Analysis\n\n## Stack & Framework\nKotlin"
    tool = AnalyzeProjectTool(fake_llm)
    result = tool.execute(path=str(spring_project))

    assert result.success
    assert "Project Analysis" in result.message
    assert "## Architecture Observations" in result.message
    assert "## Project Health" in result.message
    assert len(fake_llm.calls) == 1


def test_context_roundtrip_dict():
    from smith.tools.project_context import ProjectContext

    original = ProjectContext(
        language="Python",
        frameworks=["FastAPI"],
        build_system="Python (pyproject/setup)",
        databases=["PostgreSQL"],
        containers=["Docker"],
        ci_cd=["GitHub Actions"],
        modules=["api"],
        entry_points=["main.py"],
        architecture_layers=["api", "service"],
        detected_patterns=["Layered Architecture"],
        project_path="/tmp/proj",
        has_tests=True,
        has_build_file=True,
    )
    restored = ProjectContext.from_dict(original.to_dict())
    assert restored.language == original.language
    assert restored.frameworks == original.frameworks
