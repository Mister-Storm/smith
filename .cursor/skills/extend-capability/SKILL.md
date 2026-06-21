---
name: extend-capability
description: Adds or modifies Smith capabilities for the chat agent — triggers, evidence types, orchestrator collectors, and tests. Use when adding new chat intents, tools routed through capabilities, or expanding Smith beyond coding use cases.
---

# Extend a Smith Capability

## Checklist

```
- [ ] Define capability in capability_registry.py
- [ ] Add evidence collector(s) in context_orchestrator.py
- [ ] Update analysis_requirements.py if investigative
- [ ] Adjust grounded_response.py prompts if needed
- [ ] Unit tests for match + orchestrate + response
```

## 1. Register capability

In `smith/services/capability_registry.py`:

```python
Capability(
    "research_topic",
    ("research", "find sources", "learn about"),
    (EVIDENCE_OPTIONAL_PROJECT_CONTEXT,),  # or new EVIDENCE_* type
    analytical=True,
)
```

Use multi-word triggers for precision; set `analytical=False` for pure conversation.

## 2. Evidence collection

If reusing existing `EVIDENCE_*` constants, wire in `ContextOrchestrator._collect_*`.

For new evidence:

1. Add constant in `capability_registry.py`
2. Implement collector method in `context_orchestrator.py`
3. Register in the orchestrate dispatch map

Keep collectors **deterministic** — no LLM inside evidence gathering.

## 3. Investigative depth

If the capability reads filesystem/repositories deeply:

- Register in `analysis_requirements.is_investigative_capability`
- Ensure `context_acquisition.build_and_acquire` runs
- Validate via `evidence_validator.py`

## 4. Tests

Mirror patterns in:

- `tests/unit/test_capability_registry.py`
- `tests/unit/test_context_orchestrator.py`

Test trigger matching, evidence presence, and blocked/low-confidence paths.

## Domain-neutral examples

Good triggers: `"plan"`, `"compare"`, `"summarize"`, `"next steps"`, `"how should i"`

Avoid: `"django migration"`, `"react hook"` — keep framework detection in project context, not capability triggers.
