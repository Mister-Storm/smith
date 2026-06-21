"""DEBUG-level tracing for the investigative context pipeline."""

from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path

from smith.models.assistant import EvidenceBundle, EvidenceItem, EvidenceLevel, RepositoryKnowledge
from smith.services.repository_resolution import is_project_directory

logger = logging.getLogger(__name__)

_LEGACY_CACHE_ALIASES = frozenset({"cache", "metadata"})


def _level_counts(items: list[EvidenceItem]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for item in items:
        meta = item.metadata or {}
        raw = str(meta.get("evidence_level", "unknown"))
        if raw in _LEGACY_CACHE_ALIASES:
            counts["CACHE"] += 1
        else:
            counts[raw.upper()] += 1
    return counts


def log_repository_resolved(path: Path) -> None:
    exists = path.exists()
    is_dir = path.is_dir()
    repo_type = "project" if is_project_directory(path) else "directory" if is_dir else "missing"
    logger.debug(
        "Repository resolved:\npath=%s\nexists=%s\ntype=%s",
        path.resolve(),
        exists,
        repo_type,
    )


def log_acquisition_start(required_levels: list[EvidenceLevel]) -> None:
    levels = ", ".join(level.name for level in required_levels)
    logger.debug("Starting acquisition\nrequired_levels=[%s]", levels)


def log_collector_result(name: str, **stats) -> None:
    parts = [f"{key}={value}" for key, value in stats.items()]
    logger.debug("%s collector\n%s", name, "\n".join(parts))


def log_evidence_bundle(bundle: EvidenceBundle) -> None:
    logger.debug("Evidence bundle\nitems=%d", len(bundle.items))
    counts = _level_counts(bundle.items)
    if counts:
        lines = [f"{level}={count}" for level, count in sorted(counts.items())]
        logger.debug("Evidence levels\n%s", "\n".join(lines))


def log_orchestrator_bundle(bundle: EvidenceBundle) -> None:
    logger.debug("Bundle received from acquisition\nitems=%d", len(bundle.items))


def log_pre_llm(
    bundle: EvidenceBundle,
    knowledge: RepositoryKnowledge | None,
) -> None:
    analysis_fields: list[str] = []
    if knowledge:
        if knowledge.technologies:
            analysis_fields.append(f"technologies={len(knowledge.technologies)}")
        if knowledge.frameworks:
            analysis_fields.append(f"frameworks={len(knowledge.frameworks)}")
        if knowledge.modules:
            analysis_fields.append(f"modules={len(knowledge.modules)}")
        if knowledge.architectural_patterns:
            analysis_fields.append(f"patterns={len(knowledge.architectural_patterns)}")
    analysis = ", ".join(analysis_fields) if analysis_fields else "none"
    logger.debug(
        "Preparing LLM prompt\nevidence_items=%d\nrepository_analysis=%s",
        len(bundle.items),
        analysis,
    )


def log_session_reuse_fallback(repo: Path) -> None:
    logger.debug(
        "Session reuse skipped — no reusable evidence items matched repo path\npath=%s",
        repo.resolve(),
    )


def log_resolution_match(ref: str, source: str, path: Path) -> None:
    logger.debug(
        "Repository resolution match\nref=%s\nsource=%s\npath=%s",
        ref,
        source,
        path.resolve(),
    )
