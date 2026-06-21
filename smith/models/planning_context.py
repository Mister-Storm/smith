"""Planning context models for future Sprint 9 planning engine."""

from __future__ import annotations

from dataclasses import dataclass, field

from smith.models.git_intelligence import GitHealthReport
from smith.models.project_context import ProjectContext
from smith.models.user_context import UserContext
from smith.models.workspace import WorkspaceSummary


@dataclass(slots=True)
class PlanningContext:
    project_context: ProjectContext | None = None
    workspace_context: WorkspaceSummary | None = None
    git_context: GitHealthReport | None = None
    user_context: UserContext | None = None
    unknowns: list[str] = field(default_factory=list)
