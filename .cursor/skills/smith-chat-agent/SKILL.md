---
name: smith-chat-agent
description: Explains and modifies Smith's chat agent pipeline — intent detection, capability routing, evidence orchestration, and grounded LLM responses. Use when working on smith chat, grounded assistant, intent matching, or making Smith behave more like a generic personal operator.
---

# Smith Chat Agent

## Flow (one turn)

1. `smith/cli/commands/chat.py` → `ChatService.run()`
2. Non-slash input → `grounded_assistant.handle_message()`
3. `match_capability(message, session)` — deterministic trigger scoring
4. `repository_resolution` — paths, quoted names, sibling projects
5. `ContextOrchestrator.orchestrate()` — collect evidence, build knowledge
6. `generate_grounded_response()` — **only place LLM is invoked** for normal chat
7. Format with Rich markdown + `format_result_footer`

Slash commands skip steps 3–6 and call `slash_commands.dispatch_slash_command`.

## Key files

| File | Purpose |
|------|---------|
| `services/grounded_assistant.py` | Turn coordinator |
| `services/intent_detection.py` | References, follow-ups, location scope |
| `services/capability_registry.py` | Capability definitions |
| `services/context_orchestrator.py` | Evidence collection |
| `services/grounded_response.py` | Prompt + LLM |
| `services/assistant_session.py` | In-memory session |
| `models/assistant.py` | Dataclasses |

## Generic operator direction

When improving chat, prefer:

- New **capabilities** with broad triggers (research, plan, summarize, compare)
- **Universal planning dimensions** — not domain templates
- **Evidence types** that work outside code (documents, paths, user profile)

Avoid: LLM tool-calling loops, autonomous execution, coding-only assumptions in prompts.

## Smoke test

```bash
smith chat
# "plan a 3-month photography course"
# "analyze ." or "what is this project"
# follow-up within 5 min should reuse knowledge
```

## Tests to run

```bash
pytest tests/unit/test_intent_detection.py tests/unit/test_capability_registry.py \
  tests/unit/test_context_orchestrator.py tests/unit/test_grounded_assistant.py -q
```
