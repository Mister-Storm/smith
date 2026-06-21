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
