"""Additional tests for intent_detection coverage gaps."""

from __future__ import annotations

from pathlib import Path

from smith.models.assistant import AssistantSession
from smith.services.intent_detection import (
    extract_file_reference,
    extract_location_scope,
    extract_references,
    extract_target_path,
    has_location_hint,
    is_context_detection_intent,
    is_follow_up,
    is_knowledge_follow_up,
)


class TestIsContextDetectionIntent:
    def test_should_detect_context_intent_with_signal(self) -> None:
        assert is_context_detection_intent("identify the project context")

    def test_should_detect_context_via_type_question(self) -> None:
        assert is_context_detection_intent("what kind of project context is this")
        assert is_context_detection_intent("que tipo de contexto é este")

    def test_should_not_detect_context_without_context_keyword(self) -> None:
        assert not is_context_detection_intent("detect what folder this is")

    def test_should_not_detect_without_action(self) -> None:
        assert not is_context_detection_intent("what is the context")
        assert not is_context_detection_intent("tell me about this folder")

    def test_should_not_detect_without_context_keyword(self) -> None:
        assert not is_context_detection_intent("identify the project")
        assert not is_context_detection_intent("detect the folder")


class TestExtractReferences:
    def test_should_extract_quoted_name(self) -> None:
        refs = extract_references('check "my-project"')
        assert "my-project" in refs

    def test_should_extract_path(self) -> None:
        refs = extract_references("look at ./src/main.py")
        assert "./src/main.py" in refs

    def test_should_extract_absolute_path(self) -> None:
        refs = extract_references("analyze /home/user/project")
        assert "/home/user/project" in refs

    def test_should_extract_folder_label(self) -> None:
        refs = extract_references("check folder downloads")
        assert "downloads" in refs

    def test_should_extract_in_path_reference(self) -> None:
        refs = extract_references("look in ./src/components")
        assert "./src/components" in refs

    def test_should_detect_pascal_case_analytical(self) -> None:
        refs = extract_references("analyze BuildTwinBackend")
        assert "BuildTwinBackend" in refs

    def test_should_skip_stop_words(self) -> None:
        refs = extract_references("analyze Architecture")
        assert "Architecture" not in refs  # it's a stop word

    def test_should_skip_duplicates(self) -> None:
        refs = extract_references('analyze "my-app" and "my-app"')
        assert refs.count("my-app") == 1

    def test_should_extract_bare_name_not_in_stop_words(self) -> None:
        refs = extract_references("what about Smith")
        assert "Smith" in refs


class TestExtractTargetPath:
    def test_should_return_root_for_this_location(self, tmp_path: Path) -> None:
        result = extract_target_path("analyze this project", tmp_path)
        assert result == tmp_path.resolve()

    def test_should_return_root_for_current_folder(self, tmp_path: Path) -> None:
        result = extract_target_path("analyze this folder", tmp_path)
        assert result == tmp_path.resolve()

    def test_should_return_none_when_no_reference(self, tmp_path: Path) -> None:
        result = extract_target_path("hello", tmp_path)
        assert result is None

    def test_should_resolve_subdirectory(self, tmp_path: Path) -> None:
        sub = tmp_path / "subdir"
        sub.mkdir()
        result = extract_target_path(f"analyze {sub.name}", tmp_path)
        assert result == sub.resolve()

    def test_should_return_parent_for_sibling_scope(self, tmp_path: Path) -> None:
        result = extract_target_path("check sibling project", tmp_path)
        assert result == tmp_path.resolve().parent


class TestExtractLocationScope:
    def test_should_return_parent_for_above_patterns(self) -> None:
        from pathlib import Path

        result = extract_location_scope("one directory above", Path("/home/user/proj"))
        assert result == Path("/home/user")

    def test_should_return_parent_for_sibling(self) -> None:
        result = extract_location_scope("check sibling project", Path("/a/b"))
        assert result == Path("/a")

    def test_should_return_none_when_no_pattern(self) -> None:
        result = extract_location_scope("hello world", Path("/a"))
        assert result is None

    def test_should_handle_portuguese_patterns(self) -> None:
        result = extract_location_scope("pasta acima", Path("/home/user/proj"))
        assert result == Path("/home/user")

    def test_should_handle_ao_lado(self) -> None:
        result = extract_location_scope("projeto ao lado", Path("/x/y"))
        assert result == Path("/x")


class TestHasLocationHint:
    def test_should_return_true_for_this_location(self) -> None:
        assert has_location_hint("analyze this project", Path("/p"))

    def test_should_return_true_for_scope_pattern(self) -> None:
        assert has_location_hint("check sibling project", Path("/p"))

    def test_should_return_false_without_hint(self) -> None:
        assert not has_location_hint("hello world", Path("/p"))


class TestIsFollowUp:
    def test_should_return_false_without_session(self) -> None:
        assert not is_follow_up("tell me more", None)

    def test_should_return_false_without_last_capability(self) -> None:
        session = AssistantSession()
        assert not is_follow_up("tell me more", session)

    def test_should_return_false_for_long_messages(self) -> None:
        session = AssistantSession()
        session.last_capability_id = "analyze"
        assert not is_follow_up(
            "this is a very long message that exceeds the maximum word count for follow up detection purposes",
            session,
        )

    def test_should_detect_follow_up_signals(self) -> None:
        session = AssistantSession()
        session.last_capability_id = "analyze"
        assert is_follow_up("what about the tests", session)
        assert is_follow_up("and the architecture", session)
        assert is_follow_up("tell me more", session)

    def test_should_detect_short_follow_up_with_analysis_target(self) -> None:
        session = AssistantSession()
        session.last_capability_id = "analyze"
        session.analysis_target = Path("/target")
        assert is_follow_up("how does it work", session)


class TestIsKnowledgeFollowUp:
    def test_should_return_false_without_knowledge(self) -> None:
        session = AssistantSession()
        session.last_capability_id = "analyze"
        assert not is_knowledge_follow_up("tell me more", session)

    def test_should_return_true_with_knowledge_and_trigger(self) -> None:
        session = AssistantSession()
        session.last_capability_id = "analyze"
        session.repository_knowledge_by_path["/p"] = None  # type: ignore
        assert is_knowledge_follow_up("what about the architecture", session)

    def test_should_return_false_without_trigger_word(self) -> None:
        session = AssistantSession()
        session.last_capability_id = "analyze"
        session.repository_knowledge_by_path["/p"] = None  # type: ignore
        assert not is_knowledge_follow_up("what about the color", session)


class TestExtractFileReference:
    def test_should_return_none_without_references(self) -> None:
        assert extract_file_reference("hello", Path("/p")) is None

    def test_should_return_none_for_absolute_path(self, tmp_path: Path) -> None:
        result = extract_file_reference("/etc/passwd", tmp_path)
        assert result is None

    def test_should_return_none_for_directory_reference(self, tmp_path: Path) -> None:
        result = extract_file_reference("folder", tmp_path)
        assert result is None

    def test_should_return_file_when_exists(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.py"
        test_file.write_text("x")
        result = extract_file_reference("test.py", tmp_path)
        assert result == test_file.resolve()

    def test_should_return_none_for_nonexistent_file(self, tmp_path: Path) -> None:
        result = extract_file_reference("missing.py", tmp_path)
        assert result is None
