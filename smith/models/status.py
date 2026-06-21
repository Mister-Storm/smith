"""Status dashboard models. Used by smith status aggregation."""

from __future__ import annotations

from dataclasses import dataclass, field

from smith.models.git_intelligence import GitHealthReport
from smith.models.project_context import ProjectContext
from smith.models.workspace import WorkspaceSummary
from smith.models.workstation_health import WorkstationHealthCache
from smith.services.doctor import CheckResult


@dataclass(slots=True)
class CacheFreshness:
    label: str
    status: str
    generated_at: str | None
    refresh_command: str


@dataclass(slots=True)
class EnvironmentInfo:
    provider: str
    model: str
    memory_db: str
    config_path: str


@dataclass(slots=True)
class StatusRecommendation:
    text: str
    source: str
    command: str | None = None


@dataclass(slots=True)
class StatusReport:
    cwd: str
    environment: EnvironmentInfo
    cache_freshness: list[CacheFreshness] = field(default_factory=list)
    doctor_sections: list[tuple[str, CheckResult]] = field(default_factory=list)
    workstation_health: WorkstationHealthCache | None = None
    project_context: ProjectContext | None = None
    workspace_summary: WorkspaceSummary | None = None
    git_health: GitHealthReport | None = None
    commit_suggestion: str | None = None
    recommendations: list[StatusRecommendation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
