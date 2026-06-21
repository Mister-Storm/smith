from smith.models.assistant import EvidenceBundle
from smith.services.repository_intelligence import build_repository_knowledge
from tests.helpers.buildtwin_fixture import create_buildtwin_fixture


def _bundle_from_repo(repo):
    from smith.models.assistant import InvestigationDepth
    from smith.services.filesystem_evidence import collect_all_for_depth

    items = collect_all_for_depth(repo, InvestigationDepth.STANDARD)
    return EvidenceBundle(
        items=items,
        confidence=__import__(
            "smith.models.assistant", fromlist=["ContextConfidence"]
        ).ContextConfidence(),
    )


def test_detects_spring_boot_and_modules(tmp_path):
    repo = create_buildtwin_fixture(tmp_path)
    knowledge = build_repository_knowledge(_bundle_from_repo(repo), repo)
    assert "Spring Boot" in knowledge.frameworks or any("Spring" in f for f in knowledge.frameworks)
    assert len(knowledge.modules) >= 2
    assert any(
        "Modular" in p or "Hexagonal" in p or "DDD" in p for p in knowledge.architectural_patterns
    )


def test_quality_signals(tmp_path):
    repo = create_buildtwin_fixture(tmp_path)
    knowledge = build_repository_knowledge(_bundle_from_repo(repo), repo)
    assert any("Unit tests" in s for s in knowledge.testing_signals)
    assert any("CI" in s for s in knowledge.testing_signals)


def test_risk_and_strengths(tmp_path):
    repo = create_buildtwin_fixture(tmp_path)
    knowledge = build_repository_knowledge(_bundle_from_repo(repo), repo)
    assert knowledge.strengths
    assert knowledge.is_substantive()


def test_architecture_detector_hexagonal(tmp_path):
    repo = create_buildtwin_fixture(tmp_path)
    knowledge = build_repository_knowledge(_bundle_from_repo(repo), repo)
    patterns = " ".join(knowledge.architectural_patterns).lower()
    assert "hexagonal" in patterns or "ddd" in patterns or "modular" in patterns
