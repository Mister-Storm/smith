"""In-memory assistant session for grounded chat follow-ups."""

from __future__ import annotations

import time
from pathlib import Path

from smith.models.assistant import (
    MAX_EVIDENCE_AGE_SECONDS,
    AssistantSession,
    OrchestrationResult,
    RepositoryKnowledge,
)

_session: AssistantSession | None = None


def get_assistant_session() -> AssistantSession:
    global _session
    if _session is None:
        _session = AssistantSession()
    return _session


def reset_assistant_session() -> None:
    global _session
    _session = None


def is_knowledge_fresh(session: AssistantSession, path: Path) -> bool:
    key = str(path.resolve())
    if key not in session.repository_knowledge_by_path:
        return False
    acquired = session.knowledge_acquired_at.get(key)
    if acquired is None:
        return False
    return (time.time() - acquired) < MAX_EVIDENCE_AGE_SECONDS


def get_fresh_knowledge(session: AssistantSession, path: Path) -> RepositoryKnowledge | None:
    if is_knowledge_fresh(session, path):
        return session.repository_knowledge_by_path.get(str(path.resolve()))
    return None


def update_session_from_turn(
    session: AssistantSession,
    *,
    capability_id: str,
    result: OrchestrationResult,
    goal: str | None = None,
    knowledge_by_path: dict[str, RepositoryKnowledge] | None = None,
) -> AssistantSession:
    session.last_capability_id = capability_id
    session.last_evidence = result.bundle
    if goal:
        session.active_goal = goal
    if knowledge_by_path:
        now = time.time()
        for key, knowledge in knowledge_by_path.items():
            session.repository_knowledge_by_path[key] = knowledge
            session.knowledge_acquired_at[key] = now
            session.investigation_validated_at[key] = now
    for path in result.resolved_paths.values():
        _remember_repository(session, path)
        session.analysis_target = path
        session.active_project = path
    return session


def _remember_repository(session: AssistantSession, path: Path) -> None:
    resolved = path.resolve()
    recent = [p.resolve() for p in session.recent_repositories if p.resolve() != resolved]
    recent.insert(0, resolved)
    session.recent_repositories = recent[:10]
