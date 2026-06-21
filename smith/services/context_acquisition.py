"""Investigative context acquisition pipeline."""

from __future__ import annotations

import time
from pathlib import Path

from smith.cli.thinking_renderer import ThinkingRenderer
from smith.models.assistant import (
    MAX_EVIDENCE_AGE_SECONDS,
    AnalysisRequirements,
    AssistantSession,
    ContextConfidence,
    EvidenceBundle,
    EvidenceItem,
    EvidenceLevel,
    InvestigationReport,
    RepositoryKnowledge,
)
from smith.services.analysis_requirements import build_requirements
from smith.services.capability_registry import Capability
from smith.services.context_confidence import evaluate_confidence
from smith.services.evidence_validator import validate_requirements
from smith.services.filesystem_evidence import (
    collect_configuration,
    collect_source_samples,
    collect_structure,
)
from smith.services.investigation_trace import (
    log_acquisition_start,
    log_collector_result,
    log_evidence_bundle,
    log_session_reuse_fallback,
)
from smith.services.project_context import ProjectContextService
from smith.services.repository_intelligence import build_repository_knowledge


def acquire_evidence(
    requirements: AnalysisRequirements,
    *,
    capability: Capability,
    repo_paths: list[Path],
    session: AssistantSession,
    renderer: ThinkingRenderer | None = None,
) -> tuple[EvidenceBundle, dict[Path, RepositoryKnowledge], InvestigationReport]:
    del capability
    start = time.perf_counter()
    ui = renderer
    all_items: list[EvidenceItem] = []
    knowledge_map: dict[Path, RepositoryKnowledge] = {}
    report = InvestigationReport(repo_paths=[str(p) for p in repo_paths])

    log_acquisition_start(requirements.required_levels)

    for repo in repo_paths:
        if not repo.is_dir():
            report.problems.append(f"Repository path is not a directory: {repo}")
            continue
        key = str(repo.resolve())

        skip_filesystem = _can_reuse_validated_investigation(session, key, requirements)
        if skip_filesystem and key in session.repository_knowledge_by_path:
            reused_items: list[EvidenceItem] = []
            if session.last_evidence:
                reused_items = [
                    item
                    for item in session.last_evidence.items
                    if _item_belongs_to_repo(item, repo)
                ]
            if reused_items:
                if ui:
                    ui.complete("", f"Prior analysis reused for {repo.name}")
                knowledge_map[repo] = session.repository_knowledge_by_path[key]
                all_items.extend(reused_items)
                report.attempted.append("prior analysis reuse")
                continue
            log_session_reuse_fallback(repo)

        repo_items, repo_report = _investigate_repo(repo, requirements, ui)
        report.attempted.extend(repo_report.attempted)
        report.problems.extend(repo_report.problems)
        report.module_count += repo_report.module_count
        report.source_file_count += repo_report.source_file_count
        report.frameworks_detected.extend(repo_report.frameworks_detected)
        if repo_report.build_system and not report.build_system:
            report.build_system = repo_report.build_system
        all_items.extend(repo_items)

        hint = _optional_cache_hint(repo)
        if hint:
            all_items.append(hint)

        repo_bundle = EvidenceBundle(
            items=[i for i in all_items if _item_belongs_to_repo(i, repo)],
            confidence=ContextConfidence(),
        )
        validation = validate_requirements(
            requirements,
            repo_bundle,
            investigation_attempted=repo_report.attempted,
            problems=repo_report.problems,
        )

        has_structure = any(
            (i.metadata or {}).get("evidence_level") == EvidenceLevel.STRUCTURE.value
            for i in repo_items
            if i.source == "filesystem"
        )
        if has_structure:
            if ui:
                ui.phase("Summarizing findings...")
            knowledge = build_repository_knowledge(repo_bundle, repo)
            knowledge_map[repo] = knowledge
            if validation.sufficient:
                session.repository_knowledge_by_path[key] = knowledge
                session.knowledge_acquired_at[key] = time.time()
                session.investigation_validated_at[key] = time.time()

    resolved_path_dict = {str(p): p for p in repo_paths}
    confidence = evaluate_confidence(all_items, resolved_path_dict)
    elapsed = int((time.perf_counter() - start) * 1000)
    bundle = EvidenceBundle(
        items=all_items,
        confidence=confidence,
        tools_called=["filesystem-investigation"],
        acquisition_ms=elapsed,
    )
    log_evidence_bundle(bundle)
    return bundle, knowledge_map, report


def build_and_acquire(
    capability: Capability,
    message: str,
    *,
    repo_paths: list[Path],
    session: AssistantSession,
    renderer: ThinkingRenderer | None = None,
) -> tuple[
    EvidenceBundle,
    dict[Path, RepositoryKnowledge],
    AnalysisRequirements,
    InvestigationReport,
]:
    requirements = build_requirements(capability, message)
    bundle, knowledge, report = acquire_evidence(
        requirements,
        capability=capability,
        repo_paths=repo_paths,
        session=session,
        renderer=renderer,
    )
    return bundle, knowledge, requirements, report


def _investigate_repo(
    repo: Path,
    requirements: AnalysisRequirements,
    ui: ThinkingRenderer | None,
) -> tuple[list[EvidenceItem], InvestigationReport]:
    items: list[EvidenceItem] = []
    report = InvestigationReport()

    if ui:
        ui.phase("Inspecting project structure...")
    report.attempted.append("structure inspection")
    try:
        structure = collect_structure(repo, requirements.depth)
        items.extend(structure)
        module_count = _module_count(structure)
        report.module_count = module_count
        structure_files = [item.path or item.summary for item in structure]
        log_collector_result(
            "Structure",
            files=structure_files,
            modules=module_count,
        )
        if ui and module_count:
            ui.complete("", f"{module_count} modules detected")
        if not structure:
            report.problems.append(f"No structure evidence collected from {repo.name}")
    except OSError as exc:
        report.problems.append(f"Structure inspection failed: {exc}")

    if EvidenceLevel.CONFIGURATION in requirements.required_levels:
        if ui:
            ui.phase("Reading build configuration...")
        report.attempted.append("configuration inspection")
        try:
            config_items = collect_configuration(repo, requirements.depth)
            items.extend(config_items)
            config_signals = _config_signals(config_items)
            report.frameworks_detected.extend(config_signals["frameworks"])
            if config_signals["build_system"]:
                report.build_system = config_signals["build_system"]
            config_paths = [item.path or item.summary for item in config_items]
            log_collector_result(
                "Configuration",
                files_read=len(config_items),
                paths=config_paths[:8],
            )
            for signal in config_signals["frameworks"]:
                if ui:
                    ui.complete("", f"{signal} detected")
            if ui and config_signals["build_system"]:
                ui.complete("", f"{config_signals['build_system']} detected")
            if not config_items:
                report.problems.append(f"No configuration files found in {repo.name}")
        except OSError as exc:
            report.problems.append(f"Configuration inspection failed: {exc}")

    if EvidenceLevel.SOURCE_CODE in requirements.required_levels:
        if ui:
            ui.phase("Sampling source code...")
        report.attempted.append("source code sampling")
        try:
            source_items = collect_source_samples(repo, requirements.depth)
            items.extend(source_items)
            report.source_file_count = len(source_items)
            sampled_files = [item.path or item.summary for item in source_items]
            log_collector_result(
                "Source",
                sampled_files=sampled_files,
            )
            if ui and source_items:
                ui.complete("", f"{len(source_items)} source files analyzed")
            if not source_items:
                report.problems.append(f"No source samples collected from {repo.name}")
        except OSError as exc:
            report.problems.append(f"Source sampling failed: {exc}")

    return items, report


def _can_reuse_validated_investigation(
    session: AssistantSession,
    key: str,
    requirements: AnalysisRequirements,
) -> bool:
    if key not in session.repository_knowledge_by_path:
        return False
    validated_at = session.investigation_validated_at.get(key)
    if validated_at is None:
        return False
    if (time.time() - validated_at) >= MAX_EVIDENCE_AGE_SECONDS:
        return False
    if session.last_evidence is None:
        return False
    from smith.services.evidence_validator import validate_requirements as validate

    prior = validate(requirements, session.last_evidence)
    return prior.sufficient


def _optional_cache_hint(repo: Path) -> EvidenceItem | None:
    ctx = ProjectContextService().load(repo)
    if ctx is None:
        return None
    return EvidenceItem(
        source="project_context",
        summary=f"Optional hint for {ctx.project_name}",
        detail=ctx.to_prompt_block(),
        path=str(repo),
        metadata={"evidence_level": EvidenceLevel.CACHE.value, "hint_only": True},
    )


def _item_belongs_to_repo(item: EvidenceItem, repo: Path) -> bool:
    if item.path is None:
        return True
    try:
        Path(item.path).resolve().relative_to(repo.resolve())
        return True
    except ValueError:
        return item.path == str(repo)


def _module_count(structure_items: list[EvidenceItem]) -> int:
    for item in structure_items:
        meta = item.metadata or {}
        modules = meta.get("modules")
        if isinstance(modules, list):
            return len(modules)
        if "module" in item.summary.lower() and meta.get("entry_count"):
            return int(meta["entry_count"])
    return 0


def _config_signals(config_items: list[EvidenceItem]) -> dict[str, list[str] | str]:
    frameworks: list[str] = []
    build_system = ""
    for item in config_items:
        detail = item.detail.lower()
        path = (item.path or "").lower()
        if "spring-boot" in detail or "spring boot" in detail or "springboot" in detail:
            if "Spring Boot" not in frameworks:
                frameworks.append("Spring Boot")
        if "kotlin" in detail or path.endswith(".kts"):
            if "Gradle Kotlin DSL" not in build_system and (
                "gradle" in detail or path.endswith(".kts")
            ):
                build_system = "Gradle Kotlin DSL"
        elif "gradle" in detail or "build.gradle" in path:
            if not build_system:
                build_system = "Gradle"
        if "python" in detail or "fastapi" in detail:
            if "Python" not in frameworks:
                frameworks.append("Python")
    return {"frameworks": frameworks, "build_system": build_system}
