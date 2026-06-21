"""BuildTwin-like multi-module Kotlin/Spring fixture for investigative tests."""

from __future__ import annotations

import json
from pathlib import Path


def create_buildtwin_fixture(root: Path, *, with_cache: bool = False) -> Path:
    repo = root / "BuildTwin"
    repo.mkdir()
    (repo / "README.md").write_text("# BuildTwin\nKotlin multi-module backend.\n", encoding="utf-8")
    (repo / "settings.gradle.kts").write_text(
        'rootProject.name = "BuildTwin"\n'
        'include("app")\n'
        'include("domain")\n'
        'include("infrastructure")\n',
        encoding="utf-8",
    )
    (repo / "build.gradle.kts").write_text(
        'plugins { kotlin("jvm") id("org.springframework.boot") }\n'
        'dependencies { implementation("org.springframework.boot:spring-boot-starter") }\n',
        encoding="utf-8",
    )
    app = repo / "app" / "src" / "main" / "kotlin" / "com" / "buildtwin"
    app.mkdir(parents=True)
    (app / "Application.kt").write_text(
        '@SpringBootApplication\nclass Application\n',
        encoding="utf-8",
    )
    (app / "BuildService.kt").write_text(
        "class BuildService { fun run() = Unit }\n",
        encoding="utf-8",
    )
    domain = repo / "domain" / "src" / "main" / "kotlin" / "com" / "buildtwin" / "domain"
    domain.mkdir(parents=True)
    (domain / "BuildEntity.kt").write_text("class BuildEntity\n", encoding="utf-8")
    infra = repo / "infrastructure" / "src" / "main" / "kotlin" / "com" / "buildtwin" / "adapter"
    infra.mkdir(parents=True)
    (infra / "OutboundAdapter.kt").write_text("class OutboundAdapter\n", encoding="utf-8")
    test_dir = repo / "app" / "src" / "test" / "kotlin"
    test_dir.mkdir(parents=True)
    (test_dir / "BuildServiceTest.kt").write_text("class BuildServiceTest\n", encoding="utf-8")
    resources = repo / "app" / "src" / "main" / "resources"
    resources.mkdir(parents=True)
    (resources / "application.yml").write_text(
        "spring:\n  datasource:\n    url: jdbc:postgresql://localhost/buildtwin\n",
        encoding="utf-8",
    )
    workflows = repo / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text("name: CI\njobs:\n  test:\n    runs-on: ubuntu-latest\n", encoding="utf-8")

    if with_cache:
        smith_dir = repo / ".smith"
        smith_dir.mkdir()
        cache = {
            "schema_version": 1,
            "project_name": "BuildTwin",
            "language": "Kotlin",
            "framework": "Spring Boot",
            "build_system": "Gradle",
            "modules": ["app", "domain", "infrastructure"],
        }
        (smith_dir / "project_context.json").write_text(json.dumps(cache), encoding="utf-8")

    return repo
