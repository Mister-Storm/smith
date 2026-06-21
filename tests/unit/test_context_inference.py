import json

from smith.models.project_context import ProjectContext
from smith.services.context_inference import (
    InferenceResult,
    apply_inference,
    infer_project_context,
    parse_inference_response,
)
from tests.conftest import FakeLLMProvider


def test_parse_inference_invalid_json():
    assert parse_inference_response("not json") is None


def test_infer_with_fake_llm(tmp_path):
    from datetime import UTC, datetime

    ctx = ProjectContext(
        project_name="app",
        language="python",
        framework=None,
        build_system=None,
        database=[],
        infrastructure=[],
        ci_cd=[],
        modules=[],
        generated_at=datetime.now(UTC),
    )
    (tmp_path / "pyproject.toml").write_text("[project]\nname='app'\n")
    llm = FakeLLMProvider()
    llm._response = json.dumps(
        {
            "framework": "FastAPI",
            "database": ["sqlite"],
            "build_system": "poetry",
            "reason": "Detected fastapi dependencies",
        }
    )
    result = infer_project_context(tmp_path, ctx, workspace_confidence=0.2, provider=llm)
    assert result is not None
    assert result.framework == "FastAPI"
    assert len(llm.calls) == 1


def test_infer_disabled_when_confidence_high(tmp_path):
    from datetime import UTC, datetime

    ctx = ProjectContext(
        project_name="app",
        language="python",
        framework=None,
        build_system=None,
        database=[],
        infrastructure=[],
        ci_cd=[],
        modules=[],
        generated_at=datetime.now(UTC),
    )
    llm = FakeLLMProvider()
    result = infer_project_context(tmp_path, ctx, workspace_confidence=0.8, provider=llm)
    assert result is None
    assert len(llm.calls) == 0


def test_apply_inference_fills_gaps_only():
    from datetime import UTC, datetime

    ctx = ProjectContext(
        project_name="app",
        language="python",
        framework=None,
        build_system=None,
        database=[],
        infrastructure=[],
        ci_cd=[],
        modules=[],
        generated_at=datetime.now(UTC),
    )
    inference = InferenceResult(
        framework="FastAPI",
        build_system="poetry",
        database=["postgres"],
        reason="test",
    )
    merged = apply_inference(ctx, inference)
    assert merged.framework == "FastAPI"
    assert merged.build_system == "poetry"
    assert merged.database == ["postgres"]
