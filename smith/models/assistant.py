"""Models for the grounded assistant layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

MAX_EVIDENCE_AGE_SECONDS = 300


class ResolveStatus(StrEnum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"


class EvidenceLevel(StrEnum):
    CACHE = "cache"
    STRUCTURE = "structure"
    CONFIGURATION = "configuration"
    SOURCE_CODE = "source_code"


class InvestigationDepth(StrEnum):
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class AssistantIntent(StrEnum):
    EXPLAIN_PROJECT = "explain_project"
    ANALYZE_PROJECT = "analyze_project"
    REVIEW_ARCHITECTURE = "review_architecture"
    REVIEW_CODE = "review_code"
    COMPARE_PROJECTS = "compare_projects"
    SUMMARIZE_REPOSITORY = "summarize_repository"
    PLAN_WORK = "plan_work"
    EXPLAIN_FILE = "explain_file"
    GENERAL_CHAT = "general_chat"


@dataclass(slots=True)
class ResolveResult:
    status: ResolveStatus
    path: Path | None = None
    candidates: list[Path] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    ref: str = ""


@dataclass(slots=True)
class EvidenceItem:
    source: str
    summary: str
    detail: str
    path: str | None = None
    metadata: dict | None = None


@dataclass(slots=True)
class ContextConfidence:
    repository_identification: float = 0.0
    framework_detection: float = 0.0
    architecture_detection: float = 0.0
    project_understanding: float = 0.0

    @property
    def overall(self) -> float:
        weights = (
            self.repository_identification * 0.30
            + self.framework_detection * 0.25
            + self.architecture_detection * 0.25
            + self.project_understanding * 0.20
        )
        return round(min(1.0, max(0.0, weights)), 3)


@dataclass(slots=True)
class EvidenceBundle:
    items: list[EvidenceItem]
    confidence: ContextConfidence
    tools_called: list[str] = field(default_factory=list)
    acquisition_ms: int = 0


@dataclass(slots=True)
class RepositoryKnowledge:
    technologies: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    modules: list[str] = field(default_factory=list)
    architectural_patterns: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    testing_signals: list[str] = field(default_factory=list)
    deployment_signals: list[str] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)

    def is_substantive(self) -> bool:
        return bool(
            self.technologies
            or self.frameworks
            or self.modules
            or self.architectural_patterns
            or self.observations
        )


@dataclass(slots=True)
class AnalysisRequirements:
    intent: AssistantIntent
    required_levels: list[EvidenceLevel]
    depth: InvestigationDepth


@dataclass(slots=True)
class ValidationResult:
    sufficient: bool
    missing_levels: list[EvidenceLevel] = field(default_factory=list)
    cache_only: bool = False
    reasons: list[str] = field(default_factory=list)
    investigation_attempted: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


@dataclass(slots=True)
class InvestigationReport:
    attempted: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    repo_paths: list[str] = field(default_factory=list)
    module_count: int = 0
    source_file_count: int = 0
    frameworks_detected: list[str] = field(default_factory=list)
    build_system: str = ""


@dataclass(slots=True)
class GroundedResponse:
    answer: str
    evidence: list[EvidenceItem] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    project_overview: list[str] = field(default_factory=list)
    architecture: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    confidence: float = 0.0
    blocked: bool = False
    missing: list[str] = field(default_factory=list)
    knowledge: RepositoryKnowledge | None = None


@dataclass(slots=True)
class AssistantSession:
    active_project: Path | None = None
    active_goal: str | None = None
    recent_repositories: list[Path] = field(default_factory=list)
    analysis_target: Path | None = None
    last_capability_id: str | None = None
    last_evidence: EvidenceBundle | None = None
    repository_knowledge_by_path: dict[str, RepositoryKnowledge] = field(default_factory=dict)
    knowledge_acquired_at: dict[str, float] = field(default_factory=dict)
    investigation_validated_at: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class OrchestrationResult:
    bundle: EvidenceBundle
    session: AssistantSession
    resolved_paths: dict[str, Path] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    knowledge_by_path: dict[str, RepositoryKnowledge] = field(default_factory=dict)
    investigation: InvestigationReport | None = None
