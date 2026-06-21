"""Validate collected evidence against analysis requirements."""

from __future__ import annotations

from smith.models.assistant import (
    AnalysisRequirements,
    EvidenceBundle,
    EvidenceItem,
    EvidenceLevel,
    ValidationResult,
)
from smith.services.analysis_requirements import MANDATORY_INVESTIGATION_INTENTS

_SUBSTANTIVE_LEVELS = frozenset(
    {
        EvidenceLevel.STRUCTURE,
        EvidenceLevel.CONFIGURATION,
        EvidenceLevel.SOURCE_CODE,
    }
)

_LEGACY_CACHE_ALIASES = frozenset({"cache", "metadata"})


def _normalize_level(raw: str) -> EvidenceLevel | None:
    if raw in _LEGACY_CACHE_ALIASES:
        return EvidenceLevel.CACHE
    try:
        return EvidenceLevel(raw)
    except ValueError:
        return None


def _item_level(item: EvidenceItem) -> EvidenceLevel | None:
    meta = item.metadata or {}
    level_raw = meta.get("evidence_level")
    if level_raw:
        return _normalize_level(str(level_raw))
    if item.source in ("project_context", "optional_project_context"):
        return EvidenceLevel.CACHE
    return None


def levels_present(bundle: EvidenceBundle) -> set[EvidenceLevel]:
    present: set[EvidenceLevel] = set()
    for item in bundle.items:
        level = _item_level(item)
        if level is None:
            continue
        if level == EvidenceLevel.CACHE:
            continue
        if level in _SUBSTANTIVE_LEVELS:
            present.add(level)
    return present


def is_cache_only(bundle: EvidenceBundle) -> bool:
    substantive = levels_present(bundle)
    if substantive:
        return False
    return any(_item_level(item) == EvidenceLevel.CACHE for item in bundle.items) or bool(
        bundle.items
    )


def validate_requirements(
    requirements: AnalysisRequirements,
    bundle: EvidenceBundle,
    *,
    investigation_attempted: list[str] | None = None,
    problems: list[str] | None = None,
) -> ValidationResult:
    present = levels_present(bundle)
    missing = [level for level in requirements.required_levels if level not in present]
    cache_only = is_cache_only(bundle) and not present

    reasons: list[str] = list(problems or [])
    if missing:
        reasons.extend(f"Missing filesystem evidence: {level.value}" for level in missing)
    if cache_only and requirements.intent in MANDATORY_INVESTIGATION_INTENTS:
        reasons.append("Only cached hints available — filesystem inspection required")

    sufficient = not missing and not (
        cache_only and requirements.intent in MANDATORY_INVESTIGATION_INTENTS
    )
    return ValidationResult(
        sufficient=sufficient,
        missing_levels=missing,
        cache_only=cache_only,
        reasons=reasons,
        investigation_attempted=list(investigation_attempted or []),
        problems=list(problems or []),
    )


def is_metadata_only(bundle: EvidenceBundle) -> bool:
    """Backward-compatible alias for is_cache_only."""
    return is_cache_only(bundle)
