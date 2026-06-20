"""Workspace intelligence models. Used by future status dashboard aggregation."""

import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

WORKSPACE_SCHEMA_VERSION = 1


class ProjectStatus(StrEnum):
    ACTIVE = "Active"
    IDLE = "Idle"
    UNKNOWN = "Unknown"


@dataclass(slots=True)
class WorkspaceProject:
    """Used by future status dashboard aggregation."""

    name: str
    path: str
    language: str | None
    framework: str | None
    build_system: str | None
    branch: str | None
    last_commit_date: str | None
    last_activity: str
    modified_files: int
    status: str
    activity_score: int = 0


@dataclass(slots=True)
class WorkspaceSummary:
    """Used by future status dashboard aggregation."""

    root: str
    project_count: int
    languages: dict[str, int]
    frameworks: dict[str, int]
    active_projects: list[str]
    stale_projects: list[str]
    generated_at: str
    projects: list[WorkspaceProject]
    schema_version: int = WORKSPACE_SCHEMA_VERSION
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkspaceSummary":
        schema_version = int(data.get("schema_version", WORKSPACE_SCHEMA_VERSION))
        projects = [
            WorkspaceProject(**{k: p[k] for k in WorkspaceProject.__dataclass_fields__ if k in p})
            for p in data.get("projects", [])
        ]
        return cls(
            schema_version=schema_version,
            root=data.get("root", ""),
            project_count=data.get("project_count", len(projects)),
            languages=dict(data.get("languages", {})),
            frameworks=dict(data.get("frameworks", {})),
            active_projects=list(data.get("active_projects", [])),
            stale_projects=list(data.get("stale_projects", [])),
            generated_at=data.get("generated_at", ""),
            projects=projects,
            warnings=list(data.get("warnings", [])),
        )

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, text: str) -> "WorkspaceSummary":
        return cls.from_dict(json.loads(text))


@dataclass(slots=True)
class WorkspaceHealth:
    total_projects: int
    healthy_projects: int
    projects_without_readme: int
    projects_without_ci: int
    projects_without_tests: int
    stale_projects: int
