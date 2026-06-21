from smith.models.assistant import (
    ContextConfidence,
    EvidenceBundle,
    EvidenceItem,
)
from smith.services.capability_registry import get_capability
from smith.services.grounded_response import (
    format_blocked_response,
    format_grounded_response,
    should_generate_llm_response,
)


def _bundle(confidence: float, *, analyze_meta: dict | None = None) -> EvidenceBundle:
    items = []
    if analyze_meta is not None:
        items.append(
            EvidenceItem(
                source="analyze",
                summary="structure",
                detail="detail",
                metadata=analyze_meta,
            )
        )
    return EvidenceBundle(
        items=items,
        confidence=ContextConfidence(
            repository_identification=confidence,
            framework_detection=confidence,
            architecture_detection=confidence,
            project_understanding=confidence,
        ),
    )


def test_blocks_low_confidence_analytical():
    cap = get_capability("analyze_project")
    allowed, reasons = should_generate_llm_response(cap, _bundle(0.2))
    assert not allowed
    assert reasons


def test_allows_sufficient_structure_evidence():
    cap = get_capability("analyze_project")
    from smith.models.assistant import RepositoryKnowledge

    bundle = _bundle(0.8, analyze_meta={"language": "python", "modules": 3})
    bundle.items.extend(
        [
            EvidenceItem(
                source="filesystem",
                summary="structure",
                detail="modules",
                metadata={"evidence_level": "structure"},
            ),
            EvidenceItem(
                source="filesystem",
                summary="config",
                detail="pyproject",
                metadata={"evidence_level": "configuration"},
            ),
            EvidenceItem(
                source="filesystem",
                summary="source",
                detail="code",
                metadata={"evidence_level": "source_code"},
            ),
        ]
    )
    knowledge = RepositoryKnowledge(technologies=["Python"], modules=["api"])
    allowed, _ = should_generate_llm_response(
        cap, bundle, knowledge=knowledge, message="analyze project"
    )
    assert allowed


def test_blocks_missing_structure():
    cap = get_capability("analyze_project")
    allowed, reasons = should_generate_llm_response(cap, _bundle(0.8))
    assert not allowed
    assert any("structure" in r.lower() for r in reasons)


def test_format_blocked_includes_confidence():
    text = format_blocked_response(["missing repo"], 0.32)
    assert "32%" in text
    assert "I could not inspect the repository contents." in text
    assert "investigation attempted" in text.lower()
    assert "RepositoryKnowledge" not in text


def test_llm_allowed_without_knowledge_when_structure_present():
    cap = get_capability("analyze_project")
    bundle = _bundle(0.8)
    bundle.items.extend(
        [
            EvidenceItem(
                source="filesystem",
                summary="structure",
                detail="modules",
                metadata={"evidence_level": "structure"},
            ),
            EvidenceItem(
                source="filesystem",
                summary="config",
                detail="pyproject",
                metadata={"evidence_level": "configuration"},
            ),
        ]
    )
    allowed, reasons = should_generate_llm_response(
        cap, bundle, knowledge=None, message="analyze project"
    )
    assert allowed, reasons


def test_format_grounded_includes_sections():
    response = format_grounded_response(
        type(
            "R",
            (),
            {
                "blocked": False,
                "answer": "Done",
                "evidence": [EvidenceItem(source="filesystem", summary="s", detail="d")],
                "observations": ["obs"],
                "recommendations": ["rec"],
                "project_overview": ["Kotlin backend"],
                "architecture": ["Modular monolith"],
                "strengths": ["Clear modules"],
                "risks": ["Low tests"],
                "confidence": 0.72,
                "knowledge": None,
            },
        )()
    )
    assert "Evidence" in response
    assert "Project Overview" in response
    assert "72%" in response
