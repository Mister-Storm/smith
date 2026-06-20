from dataclasses import dataclass, field
from enum import StrEnum


class DevelopmentAssessment(StrEnum):
    CLEAN = "clean"
    READY_FOR_COMMIT = "ready_for_commit"
    WORK_IN_PROGRESS = "work_in_progress"

    @property
    def label(self) -> str:
        return {
            DevelopmentAssessment.CLEAN: "Clean",
            DevelopmentAssessment.READY_FOR_COMMIT: "Ready for Commit",
            DevelopmentAssessment.WORK_IN_PROGRESS: "Work in Progress",
        }[self]


@dataclass(slots=True)
class RepositoryStatus:
    branch: str
    modified: int
    added: int
    deleted: int
    renamed: int
    untracked: int
    staged: int
    is_clean: bool
    repo_root: str
    assessment: DevelopmentAssessment


@dataclass(slots=True)
class ChangeSummary:
    files: list[str] = field(default_factory=list)
    areas: list[str] = field(default_factory=list)
    summary_lines: list[str] = field(default_factory=list)
    llm_summary: str | None = None


@dataclass(slots=True)
class CommitSuggestion:
    message: str
    type: str
    scope: str


@dataclass(slots=True)
class ReleaseNotes:
    features: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    fixes: list[str] = field(default_factory=list)
    documentation: list[str] = field(default_factory=list)
    testing: list[str] = field(default_factory=list)
    maintenance: list[str] = field(default_factory=list)
    other: list[str] = field(default_factory=list)


@dataclass(slots=True)
class GitHealthReport:
    repo_name: str
    branch: str
    modified: int
    untracked: int
    staged: int
    recent_commits_7d: int
    largest_area: str | None
    assessment: DevelopmentAssessment
