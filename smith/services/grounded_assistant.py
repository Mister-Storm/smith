"""Coordinator for grounded chat message handling."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from smith.cli.thinking_renderer import ThinkingRenderer
from smith.core.exceptions import INVESTIGATION_FAILURE_MESSAGE, InvestigationFailure
from smith.core.formatting import format_result_footer
from smith.models.assistant import RepositoryKnowledge, ResolveStatus
from smith.services.analysis_requirements import is_investigative_capability
from smith.services.assistant_session import get_assistant_session, get_fresh_knowledge
from smith.services.capability_registry import (
    DETECT_PROJECT_CONTEXT_ID,
    GENERAL_CHAT_ID,
    get_capability,
    match_capability,
)
from smith.services.context_orchestrator import ContextOrchestrator
from smith.services.grounded_response import (
    answer_from_knowledge,
    format_grounded_response,
    generate_grounded_response,
)
from smith.services.intent_detection import (
    extract_location_scope,
    extract_references,
    extract_target_path,
    has_location_hint,
    is_knowledge_follow_up,
)
from smith.services.investigation_trace import log_repository_resolved
from smith.services.repository_resolution import (
    discover_nearby_projects,
    format_not_found_response,
    is_likely_repository_name_ref,
    resolve_references,
)
from smith.services.workspace_intelligence import WorkspaceIntelligenceService

if TYPE_CHECKING:
    from smith.services.chat import ChatService

logger = logging.getLogger(__name__)


def handle_message(
    message: str,
    *,
    chat_service: ChatService,
    session_id: str,
    renderer: ThinkingRenderer | None = None,
) -> str:
    ui = renderer or ThinkingRenderer(ui=chat_service._config.ui)
    session = get_assistant_session()

    ui.phase("Thinking...")
    capability = match_capability(message, session)

    if is_knowledge_follow_up(message, session):
        knowledge = _resolve_follow_up_knowledge(session)
        if knowledge:
            ui.complete("", "Prior analysis reused from session")
            response = answer_from_knowledge(message, knowledge)
            if response:
                body = format_grounded_response(response)
                footer = format_result_footer(
                    "chat",
                    0,
                    provider=chat_service._provider,
                    model=chat_service._model,
                )
                return f"{body}\n\n{footer}"

    ui.phase("Resolving repository...")
    workspace_cwd = chat_service._workspace
    location_scope = extract_location_scope(message, workspace_cwd)
    nearby_projects = discover_nearby_projects(workspace_cwd)
    refs = extract_references(message)
    name_refs = [ref for ref in refs if is_likely_repository_name_ref(ref)]
    resolved_paths: dict[str, Path] = {}
    missing: list[str] = []
    not_found_messages: list[str] = []
    if refs:
        discovered = WorkspaceIntelligenceService(workspace_cwd).discover_projects()
        workspace_projects = list(dict.fromkeys([*nearby_projects, *discovered]))
        resolved = resolve_references(
            refs,
            cwd=workspace_cwd,
            session=session,
            workspace_projects=workspace_projects,
            location_scope=location_scope,
        )
        for ref, result in resolved.items():
            if result.status == ResolveStatus.RESOLVED and result.path:
                resolved_paths[ref] = result.path
                log_repository_resolved(result.path)
                ui.complete("", f"{result.path.name} found")
            elif result.status == ResolveStatus.AMBIGUOUS:
                names = ", ".join(str(p) for p in result.candidates[:3])
                missing.append(f"Which repository did you mean for '{ref}'? Options: {names}")
            elif result.status == ResolveStatus.NOT_FOUND and is_likely_repository_name_ref(ref):
                not_found_messages.append(
                    format_not_found_response(
                        ref,
                        result.suggestions,
                        nearby_projects=nearby_projects,
                    )
                )

    if (
        not resolved_paths
        and is_investigative_capability(capability.id)
        and has_location_hint(message, workspace_cwd)
        and len(nearby_projects) == 1
    ):
        project = nearby_projects[0]
        resolved_paths[project.name] = project
        log_repository_resolved(project)
        ui.complete("", f"{project.name} found (nearby)")

    if capability.id == DETECT_PROJECT_CONTEXT_ID and not resolved_paths:
        target = extract_target_path(message, workspace_cwd)
        if target is not None:
            resolved_paths[target.name] = target
            log_repository_resolved(target)
            ui.complete("", f"{target.name} found")
            not_found_messages.clear()

    if not_found_messages and not resolved_paths:
        body = "\n\n".join(not_found_messages)
        footer = format_result_footer(
            "chat",
            0,
            provider=chat_service._provider,
            model=chat_service._model,
        )
        return f"{body}\n\n{footer}"

    if resolved_paths and capability.id == GENERAL_CHAT_ID:
        if any(is_likely_repository_name_ref(ref) for ref in resolved_paths):
            capability = get_capability("analyze_project")

    ui.phase("Gathering context...")
    orchestrator = ContextOrchestrator(
        cwd=chat_service._workspace,
        config=chat_service._config,
        llm=chat_service._llm,
    )
    try:
        result = orchestrator.orchestrate(
            capability,
            message=message,
            session=session,
            resolved_paths=resolved_paths,
            name_refs=name_refs,
            renderer=ui,
        )
        missing.extend(result.missing)

        if (
            result.resolved_paths
            and not result.bundle.items
            and is_investigative_capability(capability.id)
        ):
            raise InvestigationFailure(
                f"{INVESTIGATION_FAILURE_MESSAGE} "
                f"(resolved={list(result.resolved_paths.values())}, items=0)"
            )

        knowledge = _primary_knowledge(result.knowledge_by_path)

        ui.phase("Analyzing...")
        history = chat_service._memory.get_recent_messages(session_id, limit=20)

        ui.phase("Generating response...")
        response = generate_grounded_response(
            capability,
            result.bundle,
            message,
            llm=chat_service._llm,
            history=history,
            missing=missing,
            knowledge=knowledge,
            investigation=result.investigation,
        )
        body = format_grounded_response(response)
        footer = format_result_footer(
            "chat",
            result.bundle.acquisition_ms,
            provider=chat_service._provider,
            model=chat_service._model,
        )
        return f"{body}\n\n{footer}"
    except InvestigationFailure as exc:
        logger.error("Investigation pipeline failure: %s", exc)
        footer = format_result_footer(
            "chat",
            0,
            provider=chat_service._provider,
            model=chat_service._model,
        )
        return f"{INVESTIGATION_FAILURE_MESSAGE}\n\n{footer}"


def _primary_knowledge(knowledge_by_path: dict) -> RepositoryKnowledge | None:
    if not knowledge_by_path:
        return None
    return next(iter(knowledge_by_path.values()))


def _resolve_follow_up_knowledge(session) -> RepositoryKnowledge | None:
    if session.analysis_target:
        fresh = get_fresh_knowledge(session, session.analysis_target)
        if fresh:
            return fresh
    for path in session.recent_repositories:
        fresh = get_fresh_knowledge(session, path)
        if fresh:
            return fresh
    key = next(iter(session.repository_knowledge_by_path), None)
    if key:
        from smith.services.assistant_session import is_knowledge_fresh

        path = Path(key)
        if is_knowledge_fresh(session, path):
            return session.repository_knowledge_by_path[key]
    return None
