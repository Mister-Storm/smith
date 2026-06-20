from smith.services.chat import ChatService
from smith.services.slash_commands import SLASH_COMMANDS, dispatch_slash_command

EXPECTED_COMMANDS = {
    "/context",
    "/refresh-context",
    "/duplicates",
    "/organize",
    "/analyze",
    "/summarize",
    "/health",
    "/git-summary",
    "/git-changes",
    "/commit-message",
    "/release-notes",
    "/git-health",
    "/workspace",
    "/workspace-health",
    "/workspace-context",
    "/refresh-workspace-context",
}


def test_slash_command_registry_has_all_commands():
    assert set(SLASH_COMMANDS.keys()) == EXPECTED_COMMANDS
    for name in SLASH_COMMANDS:
        assert name.startswith("/")
        assert name == name.lower()


def test_dispatch_unknown_command(fake_llm, memory_service, config_with_openai):
    service = ChatService(fake_llm, memory_service, config_with_openai)
    result = dispatch_slash_command(
        service,
        "/nope",
        [],
        provider=service._provider,
        model=service._model,
    )
    assert "Unknown command" in result


def test_dispatch_empty_via_handle(fake_llm, memory_service, config_with_openai):
    service = ChatService(fake_llm, memory_service, config_with_openai)
    assert service._handle_slash_command("") == "Empty command."
