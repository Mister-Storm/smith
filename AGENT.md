# Smith — Agent Context

This document orients AI coding agents (Cursor, Claude Code, etc.) working on **Smith**: a local-first, terminal-native personal AI operator written in Python.

Read this before making architectural changes. Product principles live in [`docs/vision.md`](docs/vision.md); sprint status in [`ROADMAP.md`](ROADMAP.md).

---

## What Smith Is

Smith is a **generic personal operator**, not a coding-only assistant.

| Coding agents (Cursor, Claude Code) | Smith |
|-------------------------------------|-------|
| Optimized for repositories and IDE workflows | Optimized for **any goal** a person pursues at their workstation |
| Tool use often delegated to the LLM | **Deterministic routing** — intent and tools are chosen before the LLM |
| Broad autonomy | **Human in control** — read-only by default, no silent execution |
| Context = open files + codebase | Context = project, workspace, git, user profile, filesystem evidence |

Today Smith ships strong **developer and workstation** tools (project analysis, git intelligence, PDF summarization, planning, health scans). The architecture is deliberately **domain-agnostic** so new capabilities (research, writing, personal goals, home-lab ops) can be added without rewriting the chat loop.

**North star:** capture user intent → gather evidence → call the LLM only when needed — for *any* task, not just code.

---

## Architecture Overview

```text
User message
    │
    ▼
intent_detection ──► capability_registry.match_capability()
    │                      (deterministic triggers, not LLM)
    ▼
repository_resolution ──► resolve paths, names, sibling projects
    │
    ▼
ContextOrchestrator.orchestrate()
    │   collect evidence (structure, git, files, planning context, …)
    │   build RepositoryKnowledge when investigative
    ▼
evidence_validator + context_confidence
    │
    ▼
grounded_response.generate_grounded_response()
    │   LLM called only here (or clarification / blocked path)
    ▼
Formatted terminal response + session memory
```

**Key invariant:** the LLM does not choose tools. Capabilities declare required evidence; the orchestrator collects it deterministically.

Slash commands (`/analyze`, `/plan`, …) bypass intent matching and invoke tools explicitly via `smith/services/slash_commands.py` and `smith/services/tool_runner.py`.

---

## Repository Layout

```text
smith/
├── cli/              Typer commands, Rich UI, chat entrypoint
├── core/             Config, exceptions, formatting, logging
├── llm/              LLMProvider ABC + OpenAI / DeepSeek adapters
├── memory/           SQLite session + message persistence
├── models/           Dataclasses (assistant, planning, project, user)
├── services/         Business logic — agent pipeline lives here
└── tools/            Side-effecting operations (analyze, organize, PDF, …)

tests/
├── unit/             Fast, mocked service tests
└── integration/      CLI and pipeline tests

docs/vision.md        Product principles (authoritative)
ROADMAP.md            Sprint plan
```

### Agent pipeline (modify these together)

| Module | Role |
|--------|------|
| `services/intent_detection.py` | Reference extraction, follow-ups, location scope |
| `services/capability_registry.py` | Capability definitions + trigger scoring |
| `services/grounded_assistant.py` | Chat turn coordinator |
| `services/context_orchestrator.py` | Evidence collection orchestration |
| `services/context_acquisition.py` | Filesystem investigation depth |
| `services/repository_intelligence.py` | RepositoryKnowledge synthesis |
| `services/grounded_response.py` | Prompt assembly + LLM call |
| `services/assistant_session.py` | In-memory session state (5 min knowledge TTL) |
| `models/assistant.py` | Shared dataclasses and enums |

---

## Design Principles (non-negotiable)

1. **Deterministic first, AI last** — heuristics and cached context before tokens.
2. **Evidence before inference** — never answer analytical questions from imagination.
3. **Ask before assuming** — clarification beats hallucinated plans or structure.
4. **Explainability** — responses trace to evidence, heuristics, or cache sources.
5. **Token economy** — compact prompts; no full-repo dumps.
6. **Human remains in control** — no autonomous writes, commits, or background actions.
7. **Generic capabilities** — planning dimensions are universal (software, courses, business, personal goals). Avoid domain-specific templates.

Smith must **not** become AutoGPT, a LangGraph orchestration platform, a multi-agent framework, or a Cursor/Claude Code clone.

---

## Python Conventions

- **Python 3.12+** — use modern syntax (`list[str]`, `|` unions, `StrEnum`, `@dataclass(slots=True)`).
- **Typing** — fully typed public APIs; `from __future__ import annotations` in new modules.
- **Style** — `ruff` (line length 100, rules E/F/I/UP/B). Run `ruff check . && ruff format .` before PRs.
- **CLI** — Typer + Rich; commands stay thin, logic in `services/`.
- **LLM access** — only through `LLMProvider.generate()`; never import OpenAI clients in services except via factory.
- **Config** — `smith/core/config.py`; secrets in env only, never in TOML.
- **Tests** — pytest, ≥80% coverage on `smith/`. Prefer unit tests with fixtures in `tests/helpers/`.
- **Errors** — domain exceptions in `smith/core/exceptions.py`; user-facing messages must be actionable.

---

## Extending the Chat Agent

### Add a capability (preferred path)

1. Define triggers and required evidence in `capability_registry.py`.
2. If new evidence type: extend orchestrator collectors in `context_orchestrator.py`.
3. Add validation rules in `evidence_validator.py` / `analysis_requirements.py` if investigative.
4. Adjust prompt shaping in `grounded_response.py` if response structure changes.
5. Add unit tests for matching, orchestration, and response formatting.

Capabilities should work for **non-code domains** when possible (e.g. `plan_work` already uses universal dimensions).

### Add a CLI / slash command

1. Implement tool in `smith/tools/` returning `ToolResult`.
2. Expose via `smith/cli/commands/` and register in `smith/cli/app.py`.
3. Wire slash dispatch in `smith/services/slash_commands.py`.
4. Optionally add `tool_runner.run_*` wrapper for chat reuse.

### Add an LLM provider

1. Subclass `LLMProvider` in `smith/llm/`.
2. Register in `smith/llm/factory.py`.
3. Extend `smith setup` / `smith doctor` checks.

---

## Local Development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
smith setup          # configure provider
pytest --cov=smith --cov-fail-under=80
ruff check . && ruff format .
smith chat           # manual smoke test
```

Environment: copy `.env.example` → `.env` or use `~/.smith/env.sh`.

---

## Cursor / Agent Workflow

When working in this repo:

1. Read `docs/vision.md` for product boundaries.
2. Follow `.cursor/rules/` — especially `smith-core` (always) and `agent-pipeline` when touching services.
3. Use `.cursor/skills/` for task-specific workflows (extend capability, chat agent, dev loop).
4. Keep diffs minimal; match existing patterns in the file you edit.
5. Do not commit `.env`, `*.db`, or `.smith/` artifacts.

---

## Current Focus vs Future

**Implemented:** grounded chat, investigative repository intelligence, planning engine, user context, git/workspace/health tools.

**Planned (see ROADMAP):** context compression, user-controlled memory layer, token economics, decision context persistence, optional RAG (Sprint 16+).

When implementing future work, preserve the **intent → evidence → LLM** pipeline. New features should feel like capabilities and tools, not free-form agent loops.
