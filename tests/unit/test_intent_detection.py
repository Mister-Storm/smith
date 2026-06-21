from pathlib import Path

from smith.models.assistant import AssistantSession
from smith.services.intent_detection import (
    extract_references,
    extract_target_path,
    is_context_detection_intent,
    is_follow_up,
)


def test_extract_references_bare_name():
    refs = extract_references("analyze BuildTwin architecture")
    assert "BuildTwin" in refs


def test_extract_references_relative_path():
    refs = extract_references("check ../BuildTwin stack")
    assert any("BuildTwin" in r for r in refs)


def test_extract_references_folder_label():
    refs = extract_references("identify context of folder ../BuildTwin")
    assert any("BuildTwin" in r for r in refs)


def test_extract_target_path_this_folder(tmp_path):
    target = extract_target_path("identify context of this folder", tmp_path)
    assert target == tmp_path.resolve()


def test_extract_target_path_portuguese(tmp_path):
    target = extract_target_path("identifique o contexto desta pasta", tmp_path)
    assert target == tmp_path.resolve()


def test_is_context_detection_intent_english():
    assert is_context_detection_intent(
        "I need to identify the context of this folder through chat"
    )


def test_is_context_detection_intent_portuguese():
    assert is_context_detection_intent("identifique o contexto da pasta do projeto")


def test_is_follow_up_short_question(tmp_path):
    session = AssistantSession(
        last_capability_id="analyze_project",
        analysis_target=tmp_path,
    )
    assert is_follow_up("and the tests?", session)


def test_is_follow_up_false_without_session():
    assert not is_follow_up("what framework?", None)
