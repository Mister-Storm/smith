from pathlib import Path

from smith.models.assistant import AssistantSession
from smith.services.capability_registry import get_capability
from smith.services.context_confidence import evaluate_confidence
from smith.services.context_orchestrator import ContextOrchestrator
from smith.tools.base import ToolResult


def _tool_result(message: str, metadata: dict | None = None) -> ToolResult:
    return ToolResult(success=True, message=message, metadata=metadata or {})


def test_orchestrator_collects_analyze_evidence(tmp_path, monkeypatch):
    project = tmp_path / "app"
    project.mkdir()
    (project / "pyproject.toml").write_text("[tool.poetry]\n", encoding="utf-8")
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    monkeypatch.setattr(
        "smith.services.context_orchestrator.run_analyze",
        lambda path, llm, **kw: _tool_result(
            "# Structure",
            {"language": "python", "modules": 2, "health_score": 80},
        ),
    )
    monkeypatch.setattr(
        "smith.services.context_orchestrator.run_refresh_context",
        lambda path, **kw: _tool_result("refreshed"),
    )
    cap = get_capability("analyze_project")
    session = AssistantSession()
    orchestrator = ContextOrchestrator(cwd=project)
    result = orchestrator.orchestrate(
        cap,
        message="analyze structure",
        session=session,
        resolved_paths={"app": project},
    )
    assert result.bundle.items
    assert "filesystem-investigation" in result.bundle.tools_called
    assert result.bundle.confidence.overall > 0
    assert result.knowledge_by_path


def test_evaluate_confidence_with_analyze_metadata():
    from smith.models.assistant import EvidenceItem

    items = [
        EvidenceItem(
            source="analyze",
            summary="s",
            detail="d",
            metadata={"language": "python", "modules": 4},
        )
    ]
    conf = evaluate_confidence(items, {"ref": Path("/tmp/app")})
    assert conf.framework_detection > 0
    assert conf.architecture_detection > 0
