import json

from smith.models.planning_context import ContextGap, GapSeverity, PlanningDimension
from smith.services.planner import prioritize_gaps_with_llm
from tests.conftest import FakeLLMProvider


def _gaps() -> list[ContextGap]:
    return [
        ContextGap(
            name="Timeline",
            dimension=PlanningDimension.TIMELINE,
            reason="missing",
            severity=GapSeverity.CRITICAL,
            source="Gap Analysis",
        ),
        ContextGap(
            name="Scope",
            dimension=PlanningDimension.SCOPE,
            reason="missing",
            severity=GapSeverity.IMPORTANT,
            source="Gap Analysis",
        ),
    ]


def test_prioritize_gaps_reorders_dimensions():
    llm = FakeLLMProvider(
        response=json.dumps({"order": ["scope", "timeline"]}),
    )
    reordered = prioritize_gaps_with_llm(_gaps(), "build api", provider=llm)
    dims = [g.dimension for g in reordered if g.dimension]
    assert dims.index(PlanningDimension.SCOPE) < dims.index(PlanningDimension.TIMELINE)


def test_prioritize_gaps_rejects_new_dimensions():
    llm = FakeLLMProvider(
        response=json.dumps({"order": ["scope", "timeline", "objective"]}),
    )
    original = _gaps()
    result = prioritize_gaps_with_llm(original, "build api", provider=llm)
    assert [g.dimension for g in result if g.dimension] == [
        g.dimension for g in original if g.dimension
    ]


def test_prioritize_gaps_fallback_on_invalid_json():
    llm = FakeLLMProvider(response="not json")
    original = _gaps()
    result = prioritize_gaps_with_llm(original, "build api", provider=llm)
    assert len(result) == len(original)
