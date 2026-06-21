from smith.models.assistant import (
    AssistantIntent,
    ContextConfidence,
    EvidenceBundle,
    EvidenceItem,
    EvidenceLevel,
    InvestigationDepth,
)
from smith.services.analysis_requirements import build_requirements, required_levels_for_intent
from smith.services.capability_registry import get_capability
from smith.services.evidence_validator import is_cache_only, validate_requirements


def test_cache_never_satisfies_analyze():
    cap = get_capability("analyze_project")
    req = build_requirements(cap, "analyze project")
    bundle = EvidenceBundle(
        items=[
            EvidenceItem(
                source="project_context",
                summary="Cached hint",
                detail="hint",
                metadata={"evidence_level": EvidenceLevel.CACHE.value, "hint_only": True},
            )
        ],
        confidence=ContextConfidence(project_understanding=0.5),
    )
    result = validate_requirements(req, bundle)
    assert not result.sufficient
    assert result.cache_only


def test_analyze_requires_structure_and_config_not_source_only():
    levels = required_levels_for_intent(
        AssistantIntent.ANALYZE_PROJECT,
        InvestigationDepth.STANDARD,
    )
    assert EvidenceLevel.STRUCTURE in levels
    assert EvidenceLevel.CONFIGURATION in levels
    assert EvidenceLevel.SOURCE_CODE not in levels


def test_sufficient_with_filesystem_levels():
    cap = get_capability("analyze_project")
    req = build_requirements(cap, "analyze project")
    bundle = EvidenceBundle(
        items=[
            EvidenceItem(
                source="filesystem",
                summary="structure",
                detail="modules",
                metadata={"evidence_level": EvidenceLevel.STRUCTURE.value},
            ),
            EvidenceItem(
                source="filesystem",
                summary="build",
                detail="gradle",
                metadata={"evidence_level": EvidenceLevel.CONFIGURATION.value},
            ),
        ],
        confidence=ContextConfidence(project_understanding=0.8),
    )
    result = validate_requirements(req, bundle)
    assert result.sufficient


def test_is_cache_only_true():
    bundle = EvidenceBundle(
        items=[
            EvidenceItem(
                source="project_context",
                summary="cached",
                detail="x",
                metadata={"evidence_level": EvidenceLevel.CACHE.value},
            )
        ],
        confidence=ContextConfidence(),
    )
    assert is_cache_only(bundle)


def test_legacy_metadata_alias_treated_as_cache():
    bundle = EvidenceBundle(
        items=[
            EvidenceItem(
                source="project_context",
                summary="cached",
                detail="x",
                metadata={"evidence_level": "metadata"},
            )
        ],
        confidence=ContextConfidence(),
    )
    assert is_cache_only(bundle)
