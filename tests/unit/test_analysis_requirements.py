from smith.models.assistant import AssistantIntent, EvidenceLevel, InvestigationDepth
from smith.services.analysis_requirements import (
    build_requirements,
    capability_to_intent,
    required_levels_for_intent,
    resolve_depth,
)
from smith.services.capability_registry import get_capability


def test_capability_to_intent_analyze():
    assert capability_to_intent("analyze_project") == AssistantIntent.ANALYZE_PROJECT


def test_resolve_depth_standard_for_summarize():
    depth = resolve_depth("tell me about this repo", AssistantIntent.SUMMARIZE_REPOSITORY)
    assert depth == InvestigationDepth.STANDARD


def test_resolve_depth_deep_for_architecture_review():
    depth = resolve_depth("review architecture of the system", AssistantIntent.ANALYZE_PROJECT)
    assert depth == InvestigationDepth.DEEP


def test_required_levels_analyze_standard():
    levels = required_levels_for_intent(
        AssistantIntent.ANALYZE_PROJECT,
        InvestigationDepth.STANDARD,
    )
    assert EvidenceLevel.STRUCTURE in levels
    assert EvidenceLevel.CONFIGURATION in levels
    assert EvidenceLevel.SOURCE_CODE not in levels


def test_build_requirements_analyze():
    cap = get_capability("analyze_project")
    req = build_requirements(cap, "analyze BuildTwin and propose improvements")
    assert req.depth == InvestigationDepth.STANDARD
    assert EvidenceLevel.SOURCE_CODE in req.required_levels


def test_build_requirements_analyze_without_improvements():
    cap = get_capability("analyze_project")
    req = build_requirements(cap, "analyze BuildTwin")
    assert EvidenceLevel.SOURCE_CODE not in req.required_levels
