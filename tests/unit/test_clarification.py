from smith.models.planning_context import ContextGap, GapSeverity, PlanningDimension
from smith.services.clarification import MAX_QUESTIONS, generate_questions_from_gaps


def _gap(
    dimension: PlanningDimension | None,
    severity: GapSeverity,
    name: str = "Gap",
) -> ContextGap:
    return ContextGap(
        name=name,
        dimension=dimension,
        reason="test reason",
        severity=severity,
        source="Gap Analysis",
    )


def test_generate_questions_max_five():
    gaps = [
        _gap(PlanningDimension.TIMELINE, GapSeverity.CRITICAL),
        _gap(PlanningDimension.SUCCESS_CRITERIA, GapSeverity.CRITICAL),
        _gap(PlanningDimension.SCOPE, GapSeverity.IMPORTANT),
        _gap(PlanningDimension.STAKEHOLDERS, GapSeverity.IMPORTANT),
        _gap(PlanningDimension.CONSTRAINTS, GapSeverity.IMPORTANT),
        _gap(PlanningDimension.RESOURCES, GapSeverity.OPTIONAL),
        _gap(PlanningDimension.RISKS, GapSeverity.OPTIONAL),
    ]
    questions = generate_questions_from_gaps(gaps)
    assert len(questions) <= MAX_QUESTIONS


def test_generate_questions_maps_timeline():
    gaps = [_gap(PlanningDimension.TIMELINE, GapSeverity.CRITICAL, "Timeline")]
    questions = generate_questions_from_gaps(gaps)
    assert "timeline" in questions[0].question.lower()
    assert questions[0].reason


def test_generate_questions_prioritizes_critical():
    gaps = [
        _gap(PlanningDimension.RESOURCES, GapSeverity.OPTIONAL),
        _gap(PlanningDimension.TIMELINE, GapSeverity.CRITICAL, "Timeline"),
    ]
    questions = generate_questions_from_gaps(gaps)
    assert questions[0].id == "timeline"
