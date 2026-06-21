from smith.models.assistant import AssistantSession
from smith.services.intent_detection import extract_references, is_follow_up


def test_extract_references_bare_name():
    refs = extract_references("analyze BuildTwin architecture")
    assert "BuildTwin" in refs


def test_extract_references_relative_path():
    refs = extract_references("check ../BuildTwin stack")
    assert any("BuildTwin" in r for r in refs)


def test_is_follow_up_short_question(tmp_path):
    session = AssistantSession(
        last_capability_id="analyze_project",
        analysis_target=tmp_path,
    )
    assert is_follow_up("and the tests?", session)


def test_is_follow_up_false_without_session():
    assert not is_follow_up("what framework?", None)
