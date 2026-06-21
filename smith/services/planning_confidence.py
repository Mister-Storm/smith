"""Deterministic confidence and context quality for planning."""

from __future__ import annotations

from smith.models.git_intelligence import RepositoryStatus
from smith.models.project_context import ProjectContext
from smith.models.user_context import UserContext
from smith.models.workspace import WorkspaceSummary

MINIMUM_CONTEXT_THRESHOLD = 0.40
MIN_CONFIDENCE_FOR_PLAN = 0.55


def _user_context_quality(user_context: UserContext) -> float:
    completeness = user_context.profile_completeness / 100.0
    confidence = user_context.confidence
    return min(1.0, 0.6 * completeness + 0.4 * confidence)


def _project_context_quality(project_context: ProjectContext | None) -> float:
    if project_context is None:
        return 0.0
    fields = [
        project_context.language,
        project_context.framework,
        project_context.build_system,
    ]
    filled = sum(1 for value in fields if value)
    list_bonus = 0.0
    if project_context.database:
        list_bonus += 0.15
    if project_context.infrastructure:
        list_bonus += 0.15
    if project_context.ci_cd:
        list_bonus += 0.15
    base = filled / 3.0
    return min(1.0, base * 0.7 + list_bonus)


def _workspace_context_quality(workspace_context: WorkspaceSummary | None) -> float:
    if workspace_context is None:
        return 0.0
    if workspace_context.project_count <= 0:
        return 0.2
    score = min(1.0, workspace_context.project_count / 5.0)
    if workspace_context.languages:
        score = min(1.0, score + 0.2)
    if workspace_context.frameworks:
        score = min(1.0, score + 0.2)
    return score


def _git_context_quality(git_context: RepositoryStatus | None) -> float:
    if git_context is None:
        return 0.0
    score = 0.7
    if git_context.is_clean:
        score = min(1.0, score + 0.3)
    return score


def calculate_context_quality(
    user_context: UserContext,
    project_context: ProjectContext | None,
    workspace_context: WorkspaceSummary | None,
    git_context: RepositoryStatus | None,
) -> float:
    user_q = _user_context_quality(user_context)
    project_q = _project_context_quality(project_context)
    workspace_q = _workspace_context_quality(workspace_context)
    git_q = _git_context_quality(git_context)
    return round(0.40 * user_q + 0.30 * project_q + 0.20 * workspace_q + 0.10 * git_q, 3)


def calculate_confidence(
    context_quality: float,
    known_count: int,
    critical_gap_count: int,
    important_gap_count: int,
    assumption_count: int,
) -> float:
    known_bonus = min(0.25, known_count * 0.04)
    critical_penalty = min(0.30, critical_gap_count * 0.10)
    important_penalty = min(0.20, important_gap_count * 0.05)
    assumption_penalty = min(0.25, assumption_count * 0.08)
    raw = (
        context_quality
        + known_bonus
        - critical_penalty
        - important_penalty
        - assumption_penalty
    )
    return round(max(0.0, min(1.0, raw)), 3)
