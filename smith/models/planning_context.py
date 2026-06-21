"""Planning context models for the guided planning engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from smith.models.git_intelligence import RepositoryStatus
from smith.models.project_context import ProjectContext
from smith.models.user_context import UserContext
from smith.models.workspace import WorkspaceSummary


class PlanningDimension(StrEnum):
    OBJECTIVE = "objective"
    SUCCESS_CRITERIA = "success_criteria"
    SCOPE = "scope"
    CONSTRAINTS = "constraints"
    STAKEHOLDERS = "stakeholders"
    TIMELINE = "timeline"
    RESOURCES = "resources"
    RISKS = "risks"


class GapSeverity(StrEnum):
    CRITICAL = "critical"
    IMPORTANT = "important"
    OPTIONAL = "optional"


@dataclass(slots=True)
class PlanningKnown:
    text: str
    source: str
    evidence: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PlanningConstraint:
    text: str
    source: str


@dataclass(slots=True)
class ContextGap:
    name: str
    dimension: PlanningDimension | None
    reason: str
    severity: GapSeverity
    source: str


@dataclass(slots=True)
class PlanningDecision:
    """Explicit user answer for a planning dimension (session-scoped in Sprint 9.2)."""

    dimension: PlanningDimension
    answer: str
    recorded_at: str


@dataclass(slots=True)
class PlanningContext:
    user_context: UserContext
    project_context: ProjectContext | None = None
    workspace_context: WorkspaceSummary | None = None
    git_context: RepositoryStatus | None = None
    knowns: list[PlanningKnown] = field(default_factory=list)
    gaps: list[ContextGap] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    constraints: list[PlanningConstraint] = field(default_factory=list)
    decisions: list[PlanningDecision] = field(default_factory=list)
    goal: str | None = None


@dataclass(slots=True)
class PlanRequest:
    goal: str


@dataclass(slots=True)
class ClarificationQuestion:
    id: str
    question: str
    reason: str


@dataclass(slots=True)
class PlanningResult:
    goal: str
    knowns: list[PlanningKnown]
    gaps: list[ContextGap]
    assumptions: list[str]
    constraints: list[PlanningConstraint]
    decisions: list[PlanningDecision]
    questions: list[ClarificationQuestion]
    plan: str | None
    confidence: float
    planning_mode: str


@dataclass(slots=True)
class PlanningReadiness:
    known_count: int
    gap_count: int
    critical_gap_count: int
    important_gap_count: int
    assumption_count: int
    constraint_count: int
    context_quality: float
    confidence: float
    status: str


@dataclass(slots=True)
class PlanningSession:
    """In-memory planning session for interactive loop."""

    goal: str
    gaps: list[ContextGap] = field(default_factory=list)
    decisions: list[PlanningDecision] = field(default_factory=list)
    questions: list[ClarificationQuestion] = field(default_factory=list)
    last_result: PlanningResult | None = None
