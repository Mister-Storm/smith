from smith.cli.thinking_renderer import ThinkingRenderer
from smith.core.config import Config, UIConfig
from smith.models.assistant import AssistantSession, RepositoryKnowledge
from smith.services.assistant_session import (
    get_assistant_session,
    is_knowledge_fresh,
)
from smith.services.grounded_response import answer_from_knowledge, format_grounded_response
from tests.helpers.buildtwin_fixture import create_buildtwin_fixture


def test_thinking_renderer_phase_and_complete(capsys):
    renderer = ThinkingRenderer(enabled=True, ui=UIConfig())
    renderer.phase("Inspecting...")
    renderer.complete("Structure", "7 modules detected")
    captured = capsys.readouterr()
    assert "Inspecting" in captured.out
    assert "7 modules detected" in captured.out


def test_ui_config_defaults():
    config = Config.load(load_env=False)
    assert config.ui.assistant_color == "bright_cyan"
    assert config.ui.success_color == "green"


def test_answer_from_knowledge_framework():
    knowledge = RepositoryKnowledge(
        frameworks=["Spring Boot"],
        technologies=["Kotlin"],
        architectural_patterns=["Modular Monolith"],
    )
    response = answer_from_knowledge("What framework does it use?", knowledge)
    assert response is not None
    assert "Spring Boot" in response.answer


def test_knowledge_follow_up_freshness(tmp_path):
    repo = create_buildtwin_fixture(tmp_path)
    session = get_assistant_session()
    knowledge = RepositoryKnowledge(frameworks=["Spring Boot"], risks=["Low test coverage"])
    key = str(repo.resolve())
    session.repository_knowledge_by_path[key] = knowledge
    import time

    session.knowledge_acquired_at[key] = time.time()
    assert is_knowledge_fresh(session, repo)


def test_investigative_acquire_buildtwin(tmp_path):
    from smith.services.analysis_requirements import build_requirements
    from smith.services.capability_registry import get_capability
    from smith.services.context_acquisition import acquire_evidence

    repo = create_buildtwin_fixture(tmp_path)
    cap = get_capability("analyze_project")
    req = build_requirements(cap, "analyze BuildTwin and propose improvements")
    session = AssistantSession()
    bundle, knowledge_map, _report = acquire_evidence(
        req,
        capability=cap,
        repo_paths=[repo],
        session=session,
        renderer=ThinkingRenderer(enabled=False),
    )
    assert bundle.items
    assert repo in knowledge_map
    assert knowledge_map[repo].is_substantive()


def test_format_structured_response():
    knowledge = RepositoryKnowledge(
        technologies=["Kotlin"],
        frameworks=["Spring Boot"],
        architectural_patterns=["Modular Monolith"],
        strengths=["Clear module separation"],
        risks=["No coverage enforcement found"],
    )
    from smith.models.assistant import GroundedResponse

    text = format_grounded_response(
        GroundedResponse(
            answer="Summary",
            project_overview=["Kotlin backend"],
            architecture=["Modular Monolith"],
            strengths=knowledge.strengths,
            risks=knowledge.risks,
            recommendations=["Add coverage gates"],
            confidence=0.8,
            knowledge=knowledge,
        )
    )
    assert "Project Overview" in text
    assert "Architecture" in text
    assert "Risks" in text
    assert "Recommendations" in text
