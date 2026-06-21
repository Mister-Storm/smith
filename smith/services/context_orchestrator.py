"""Reusable evidence collection for all grounded assistant flows."""

from __future__ import annotations

import time
from pathlib import Path

from smith.core.config import Config
from smith.llm.base import LLMProvider
from smith.models.assistant import (
    AssistantSession,
    ContextConfidence,
    EvidenceBundle,
    EvidenceItem,
    EvidenceLevel,
    OrchestrationResult,
    ResolveStatus,
)
from smith.services.analysis_requirements import is_investigative_capability
from smith.services.assistant_session import update_session_from_turn
from smith.services.capability_registry import (
    EVIDENCE_FILE_CONTENTS,
    EVIDENCE_GIT_CHANGES,
    EVIDENCE_GIT_SUMMARY,
    EVIDENCE_OPTIONAL_PROJECT_CONTEXT,
    EVIDENCE_PLANNING_CONTEXT,
    EVIDENCE_PROJECT_CONTEXT,
    EVIDENCE_PROJECT_STRUCTURE,
    Capability,
)
from smith.services.context_acquisition import build_and_acquire
from smith.services.context_confidence import evaluate_confidence
from smith.services.git_intelligence import (
    GitIntelligenceService,
    format_git_changes,
    format_git_summary,
)
from smith.services.capability_registry import DETECT_PROJECT_CONTEXT_ID
from smith.services.intent_detection import (
    extract_file_reference,
    extract_location_scope,
    extract_references,
    extract_target_path,
)
from smith.services.investigation_trace import log_orchestrator_bundle
from smith.services.planner import PlanningService, format_planning_explain
from smith.services.project_context import ProjectContextService, format_context_text
from smith.services.repository_resolution import (
    is_likely_repository_name_ref,
    resolve_references,
)
from smith.services.tool_runner import run_analyze, run_refresh_context
from smith.services.workspace_intelligence import WorkspaceIntelligenceService

MAX_FILE_BYTES = 8192


def _resolve_repo_paths(
    paths: dict[str, Path],
    primary: Path | None,
    cwd: Path,
    *,
    name_refs: list[str] | None = None,
) -> list[Path]:
    if paths:
        return list(paths.values())[:2]
    if primary:
        return [primary]
    if name_refs:
        return []
    if cwd.is_dir():
        return [cwd]
    return []


class ContextOrchestrator:
    def __init__(
        self,
        *,
        cwd: Path,
        config: Config | None = None,
        llm: LLMProvider | None = None,
    ) -> None:
        self._cwd = cwd.resolve()
        self._config = config or Config.load()
        self._llm = llm
        self._project_service = ProjectContextService()
        self._workspace_service = WorkspaceIntelligenceService(self._cwd)

    def orchestrate(
        self,
        capability: Capability,
        *,
        message: str,
        session: AssistantSession,
        resolved_paths: dict[str, Path] | None = None,
        name_refs: list[str] | None = None,
        renderer=None,
    ) -> OrchestrationResult:
        start = time.perf_counter()
        paths = dict(resolved_paths or {})
        missing: list[str] = []
        knowledge_by_path: dict[str, object] = {}

        primary = self._primary_path(
            paths, session, message=message, capability_id=capability.id
        )
        refs = extract_references(message)
        extracted_name_refs = [ref for ref in refs if is_likely_repository_name_ref(ref)]
        effective_name_refs = name_refs if name_refs is not None else extracted_name_refs
        location_scope = extract_location_scope(message, self._cwd)
        if not paths and refs:
            workspace_projects = self._workspace_service.discover_projects()
            from smith.services.repository_resolution import discover_nearby_projects

            merged_projects = list(
                dict.fromkeys([*discover_nearby_projects(self._cwd), *workspace_projects])
            )
            resolved = resolve_references(
                refs,
                cwd=self._cwd,
                session=session,
                workspace_projects=merged_projects,
                location_scope=location_scope,
            )
            for ref, result in resolved.items():
                if result.status == ResolveStatus.RESOLVED and result.path:
                    paths[ref] = result.path
                elif result.status == ResolveStatus.AMBIGUOUS:
                    names = ", ".join(str(p) for p in result.candidates[:3])
                    missing.append(f"Ambiguous repository '{ref}': {names}")

        if capability.id == "compare_projects" and len(paths) < 2:
            for ref in refs:
                if ref not in paths:
                    missing.append(f"Could not resolve project reference: {ref}")

        if is_investigative_capability(capability.id):
            repo_paths = _resolve_repo_paths(
                paths,
                primary,
                self._cwd,
                name_refs=effective_name_refs,
            )
            from smith.models.assistant import InvestigationReport
            from smith.services.evidence_validator import validate_requirements

            if not repo_paths:
                report = InvestigationReport(
                    problems=["Repository path not resolved for investigation"]
                )
                result = OrchestrationResult(
                    bundle=EvidenceBundle(items=[], confidence=ContextConfidence()),
                    session=session,
                    resolved_paths=paths,
                    missing=["Repository path not resolved"],
                    investigation=report,
                )
                update_session_from_turn(
                    session,
                    capability_id=capability.id,
                    result=result,
                )
                return result

            bundle, knowledge_map, requirements, investigation = build_and_acquire(
                capability,
                message,
                repo_paths=repo_paths,
                session=session,
                renderer=renderer,
            )
            log_orchestrator_bundle(bundle)
            validation = validate_requirements(
                requirements,
                bundle,
                investigation_attempted=investigation.attempted,
                problems=investigation.problems,
            )
            if not validation.sufficient:
                missing.extend(validation.reasons)
            knowledge_by_path = {str(k): v for k, v in knowledge_map.items()}
            elapsed = int((time.perf_counter() - start) * 1000)
            bundle.acquisition_ms = elapsed
            result = OrchestrationResult(
                bundle=bundle,
                session=session,
                resolved_paths=paths,
                missing=missing,
                knowledge_by_path=knowledge_by_path,
                investigation=investigation,
            )
            update_session_from_turn(
                session,
                capability_id=capability.id,
                result=result,
                goal=message if capability.id == "plan_work" else None,
                knowledge_by_path=knowledge_by_path,
            )
            return result

        items: list[EvidenceItem] = []
        tools_called: list[str] = []

        for evidence_type in capability.required_evidence:
            collected, tool, gap = self._collect_evidence(
                evidence_type,
                capability_id=capability.id,
                message=message,
                primary=primary,
                paths=paths,
                session=session,
            )
            if collected:
                items.extend(collected)
            if tool:
                tools_called.append(tool)
            if gap:
                missing.extend(gap)

        confidence = evaluate_confidence(items, paths)
        elapsed = int((time.perf_counter() - start) * 1000)
        bundle = EvidenceBundle(
            items=items,
            confidence=confidence,
            tools_called=tools_called,
            acquisition_ms=elapsed,
        )
        result = OrchestrationResult(
            bundle=bundle,
            session=session,
            resolved_paths=paths,
            missing=missing,
        )
        update_session_from_turn(
            session,
            capability_id=capability.id,
            result=result,
            goal=message if capability.id == "plan_work" else None,
        )
        return result

    def _primary_path(
        self,
        paths: dict[str, Path],
        session: AssistantSession,
        *,
        message: str = "",
        capability_id: str = "",
    ) -> Path | None:
        if paths:
            return next(iter(paths.values()))
        if capability_id == DETECT_PROJECT_CONTEXT_ID:
            target = extract_target_path(message, self._cwd)
            if target is not None:
                return target
        if session.analysis_target:
            return session.analysis_target
        if session.active_project:
            return session.active_project
        if self._project_service.load(self._cwd):
            return self._cwd
        return self._cwd if capability_id == DETECT_PROJECT_CONTEXT_ID else None

    def _collect_evidence(
        self,
        evidence_type: str,
        *,
        capability_id: str,
        message: str,
        primary: Path | None,
        paths: dict[str, Path],
        session: AssistantSession,
    ) -> tuple[list[EvidenceItem], str | None, list[str]]:
        if evidence_type == EVIDENCE_PROJECT_STRUCTURE:
            return self._collect_project_structure(primary, paths)
        if evidence_type == EVIDENCE_GIT_CHANGES:
            return self._collect_git_changes(primary)
        if evidence_type == EVIDENCE_FILE_CONTENTS:
            return self._collect_file_contents(message, primary)
        if evidence_type == EVIDENCE_PROJECT_CONTEXT:
            force_refresh = capability_id == DETECT_PROJECT_CONTEXT_ID
            return self._collect_project_context(primary, paths, force_refresh=force_refresh)
        if evidence_type == EVIDENCE_PLANNING_CONTEXT:
            return self._collect_planning_context(message)
        if evidence_type == EVIDENCE_GIT_SUMMARY:
            return self._collect_git_summary(primary)
        if evidence_type == EVIDENCE_OPTIONAL_PROJECT_CONTEXT:
            return self._collect_optional_project_context(primary)
        return [], None, []

    def _collect_project_structure(
        self,
        primary: Path | None,
        paths: dict[str, Path],
    ) -> tuple[list[EvidenceItem], str | None, list[str]]:
        target = primary or self._cwd
        if not target.is_dir():
            return [], None, ["No project directory resolved for structure analysis"]
        result = run_analyze(target, None, structure_only=True)
        if not result.success:
            refresh = run_refresh_context(target)
            if refresh.success:
                result = run_analyze(target, None, structure_only=True)
        if not result.success:
            return [], "analyze", [result.message]
        meta = result.metadata or {}
        return (
            [
                EvidenceItem(
                    source="analyze",
                    summary=f"Project structure for {target.name}",
                    detail=result.message[:4000],
                    path=str(target),
                    metadata=meta,
                )
            ],
            "analyze",
            [],
        )

    def _collect_git_changes(
        self,
        primary: Path | None,
    ) -> tuple[list[EvidenceItem], str | None, list[str]]:
        target = primary or self._cwd
        try:
            git = GitIntelligenceService(cwd=target)
            summary = git.summarize_changes()
            text = format_git_changes(summary)
        except Exception as exc:
            return [], None, [f"Git changes unavailable: {exc}"]
        return (
            [
                EvidenceItem(
                    source="git",
                    summary="Repository change summary",
                    detail=text,
                    path=str(target),
                )
            ],
            "git-changes",
            [],
        )

    def _collect_file_contents(
        self,
        message: str,
        primary: Path | None,
    ) -> tuple[list[EvidenceItem], str | None, list[str]]:
        cwd = primary or self._cwd
        file_path = extract_file_reference(message, cwd)
        if file_path is None:
            return [], None, ["No file path found in message"]
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")[:MAX_FILE_BYTES]
        except OSError as exc:
            return [], None, [f"Could not read file: {exc}"]
        return (
            [
                EvidenceItem(
                    source="file",
                    summary=f"Contents of {file_path.name}",
                    detail=content,
                    path=str(file_path),
                )
            ],
            "read-file",
            [],
        )

    def _collect_project_context(
        self,
        primary: Path | None,
        paths: dict[str, Path],
        *,
        force_refresh: bool = False,
    ) -> tuple[list[EvidenceItem], str | None, list[str]]:
        targets = list(paths.values()) if paths else ([primary] if primary else [self._cwd])
        items: list[EvidenceItem] = []
        gaps: list[str] = []
        for target in targets[:2]:
            ctx = None if force_refresh else self._project_service.load(target)
            if ctx is None:
                refresh = run_refresh_context(target)
                if refresh.success and refresh.metadata:
                    from smith.models.project_context import ProjectContext

                    ctx = ProjectContext.from_dict(refresh.metadata["context"])
            if ctx is None:
                gaps.append(f"No project context for {target}")
                continue
            items.append(
                EvidenceItem(
                    source="project_context",
                    summary=f"Cached hint for {ctx.project_name}",
                    detail=format_context_text(ctx),
                    path=str(target),
                    metadata={
                        "evidence_level": EvidenceLevel.CACHE.value,
                        "hint_only": True,
                        "language": ctx.language,
                        "framework": ctx.framework,
                        "modules": len(ctx.modules),
                    },
                )
            )
        return items, "project-context", gaps

    def _collect_planning_context(
        self,
        message: str,
    ) -> tuple[list[EvidenceItem], str | None, list[str]]:
        service = PlanningService(cwd=self._cwd, config=self._config, provider=self._llm)
        ctx = service.build_context(message)
        _, confidence, gaps = service.evaluate_readiness(ctx)
        detail = format_planning_explain(ctx, gaps=gaps)
        return (
            [
                EvidenceItem(
                    source="planning",
                    summary=f"Planning context (confidence {confidence:.0%})",
                    detail=detail,
                    metadata={"confidence": confidence, "gap_count": len(gaps)},
                )
            ],
            "planning",
            [],
        )

    def _collect_git_summary(
        self,
        primary: Path | None,
    ) -> tuple[list[EvidenceItem], str | None, list[str]]:
        target = primary or self._cwd
        try:
            git = GitIntelligenceService(cwd=target)
            status = git.get_repository_status()
            suggestions = git.suggest_commit_messages()
            areas = git.summarize_changes().areas
            text = format_git_summary(status, suggestions, areas=areas)
        except Exception as exc:
            return [], None, [f"Git summary unavailable: {exc}"]
        return (
            [
                EvidenceItem(
                    source="git",
                    summary="Repository summary",
                    detail=text,
                    path=str(target),
                )
            ],
            "git-summary",
            [],
        )

    def _collect_optional_project_context(
        self,
        primary: Path | None,
    ) -> tuple[list[EvidenceItem], str | None, list[str]]:
        target = primary or self._cwd
        ctx = self._project_service.load(target)
        if ctx is None:
            return [], None, []
        return (
            [
                EvidenceItem(
                    source="project_context",
                    summary=f"Cached hint for {ctx.project_name}",
                    detail=ctx.to_prompt_block(),
                    path=str(target),
                    metadata={
                        "evidence_level": EvidenceLevel.CACHE.value,
                        "hint_only": True,
                        "language": ctx.language,
                        "framework": ctx.framework,
                    },
                )
            ],
            None,
            [],
        )
