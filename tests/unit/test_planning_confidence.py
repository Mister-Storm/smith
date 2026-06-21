from smith.services.planning_confidence import calculate_confidence


def test_calculate_confidence_penalizes_gaps_and_assumptions():
    base = calculate_confidence(
        0.7, known_count=5, critical_gap_count=0, important_gap_count=1, assumption_count=0
    )
    worse = calculate_confidence(
        0.7, known_count=5, critical_gap_count=2, important_gap_count=3, assumption_count=3
    )
    assert worse < base
