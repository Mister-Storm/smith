from smith.models.assistant import ContextConfidence, EvidenceBundle


def test_context_confidence_overall_weighted():
    conf = ContextConfidence(
        repository_identification=1.0,
        framework_detection=0.8,
        architecture_detection=0.6,
        project_understanding=0.7,
    )
    assert 0.0 < conf.overall <= 1.0


def test_context_confidence_clamped():
    conf = ContextConfidence(
        repository_identification=2.0,
        framework_detection=2.0,
        architecture_detection=2.0,
        project_understanding=2.0,
    )
    assert conf.overall == 1.0


def test_evidence_bundle_carries_confidence():
    conf = ContextConfidence(repository_identification=0.5)
    bundle = EvidenceBundle(items=[], confidence=conf)
    assert bundle.confidence.repository_identification == 0.5
