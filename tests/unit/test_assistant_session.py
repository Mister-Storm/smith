from smith.models.assistant import (
    ContextConfidence,
    EvidenceBundle,
    OrchestrationResult,
)
from smith.services.assistant_session import (
    get_assistant_session,
    reset_assistant_session,
    update_session_from_turn,
)


def test_session_singleton():
    reset_assistant_session()
    a = get_assistant_session()
    b = get_assistant_session()
    assert a is b


def test_update_session_remembers_repository(tmp_path):
    reset_assistant_session()
    session = get_assistant_session()
    project = tmp_path / "BuildTwin"
    project.mkdir()
    bundle = EvidenceBundle(items=[], confidence=ContextConfidence())
    result = OrchestrationResult(
        bundle=bundle,
        session=session,
        resolved_paths={"BuildTwin": project.resolve()},
    )
    update_session_from_turn(session, capability_id="analyze_project", result=result)
    assert session.analysis_target == project.resolve()
    assert project.resolve() in session.recent_repositories
