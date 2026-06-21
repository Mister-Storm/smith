from smith.models.planning_context import ContextGap, GapSeverity, PlanningDimension
from smith.services.clarification import generate_questions_from_gaps, has_blocking_gaps


def _gap(dimension: PlanningDimension, severity: GapSeverity) -> ContextGap:
    return ContextGap(
        name=dimension.value,
        dimension=dimension,
        reason="reason",
        severity=severity,
        source="Gap Analysis",
    )


def test_questions_from_gaps_respects_severity_order():
    gaps = [
        _gap(PlanningDimension.RESOURCES, GapSeverity.OPTIONAL),
        _gap(PlanningDimension.TIMELINE, GapSeverity.CRITICAL),
        _gap(PlanningDimension.SCOPE, GapSeverity.IMPORTANT),
    ]
    questions = generate_questions_from_gaps(gaps)
    assert questions[0].id == "timeline"


def test_has_blocking_gaps_detects_important():
    gaps = [_gap(PlanningDimension.SCOPE, GapSeverity.IMPORTANT)]
    assert has_blocking_gaps(gaps)


def test_has_blocking_gaps_ignores_optional_only():
    gaps = [_gap(PlanningDimension.RISKS, GapSeverity.OPTIONAL)]
    assert not has_blocking_gaps(gaps)
