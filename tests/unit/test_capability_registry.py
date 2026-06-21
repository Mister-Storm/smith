from smith.models.assistant import AssistantSession
from smith.services.capability_registry import (
    GENERAL_CHAT_ID,
    match_capability,
)


def test_match_analyze_project():
    cap = match_capability("analyze the project architecture")
    assert cap.id == "analyze_project"


def test_match_analyze_project_portuguese():
    cap = match_capability("analise o projeto buildTwin-frontend e proponha melhorias")
    assert cap.id == "analyze_project"


def test_match_review_code():
    cap = match_capability("review code changes")
    assert cap.id == "review_code"


def test_match_plan_work():
    cap = match_capability("plan next steps for the api")
    assert cap.id == "plan_work"


def test_match_general_fallback():
    cap = match_capability("hello there")
    assert cap.id == GENERAL_CHAT_ID


def test_follow_up_reuses_last_capability():
    session = AssistantSession(last_capability_id="analyze_project")
    cap = match_capability("what about tests?", session)
    assert cap.id == "analyze_project"
