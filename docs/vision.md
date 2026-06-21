# Smith Product Vision

Smith is a local-first workstation assistant that uses AI selectively, minimizes token consumption, preserves context efficiently, and prefers deterministic behavior whenever possible.

This document is the architectural north star for future development.

---

## Mission

Smith is:

- **Local-first** — your shell and filesystem are the control plane; context lives on your machine
- **Developer-friendly** — built for people who work in terminals and codebases daily
- **Workstation-oriented** — focused on hygiene, context, and clarity across projects — not generic chat
- **Cost-aware** — every AI call should earn its place; token usage is a design constraint
- **Explainable** — recommendations trace back to evidence, heuristics, or cached context

Smith must **not** evolve into AutoGPT, a LangGraph orchestration platform, an autonomous agent framework, a multi-agent experimentation project, a Cursor clone, or a Claude Code clone.

---

## Core Principles

### 1. AI Last, Not AI First

Preferred decision hierarchy:

```text
Deterministic Logic
↓
Simple Heuristics
↓
AI Reasoning
```

AI should only be used when simpler approaches cannot solve the problem adequately.

---

### 2. Context Is a Product

Smith's value is not model access.

Its value comes from understanding:

- project context
- workspace context
- git context
- user context
- conversation context

Context quality is more important than model size.

---

### 3. Token Economy Matters

Every AI feature should consider:

- prompt size
- context size
- estimated cost
- compression opportunities

Token efficiency is a first-class concern.

---

### 4. Ask Before Assuming

When information is missing:

- ask questions
- expose uncertainty
- avoid assumptions

Smith should prefer clarification over invention.

---

### 5. Human Remains In Control

No autonomous actions.

No self-directed execution.

No background automation without explicit user intent.

---

### 6. Explainability

Every recommendation should be traceable to:

- detected evidence
- heuristic
- context source

---

### 7. Incremental Understanding

Preferred workflow:

```text
Understand
→ Clarify
→ Plan
→ Execute
```

Never:

```text
Assume
→ Generate
→ Hope
```

Smith should accumulate understanding gradually rather than generating solutions from incomplete information.

---

## User Understanding

Smith should learn useful context about the user over time.

The goal is not storing everything.

The goal is maintaining a concise model of:

- interests
- goals
- preferred technologies
- active work

User context should be:

- **Editable** — manual overrides via `smith profile set-interest` and `smith profile set-goal`
- **Explainable** — every derived field traceable via `smith profile explain`
- **Compressible** — concise representation for future planning and token-efficient prompts

See `smith profile` and [ROADMAP.md](../ROADMAP.md) Sprint 8.

---

## Guided Planning

Smith should not create plans from incomplete information.

Smith does not plan from templates. Smith plans from context.

Planning is based on:

- Known facts (evidence-backed)
- Context gaps (universal dimensions)
- Explicit user decisions (user-provided answers)

The planner:

1. Identifies what is known
2. Identifies what is missing
3. Explains why missing information matters
4. Requests clarification
5. Incorporates user answers and rebuilds context
6. Generates plans only when sufficient evidence exists

Planning dimensions are universal — they apply to software, books, courses, businesses, and personal goals alike. Never on domain templates.

When uncertainty is high, Smith asks clarifying questions before generating a plan. Plans are generated only when deterministic guardrails pass.

Use `smith plan`, `smith plan answer`, `smith plan-status`, and `smith plan explain`. See [ROADMAP.md](../ROADMAP.md) Sprint 9.

### Core Planning Principles

1. **Evidence before inference** — known facts include source and evidence where available
2. **Ask before assuming** — clarification questions when critical or important gaps remain
3. **Deterministic first, AI second** — context assembly and readiness scoring are reproducible
4. **Context before planning** — cached context must exist before plan generation
5. **Minimize token consumption** — compact prompts only; no full repository dumps
6. **Read-only by default** — planning never modifies files or executes tasks
7. **No autonomous execution** — Smith supports decisions; the user remains in control
