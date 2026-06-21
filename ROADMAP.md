# Smith Roadmap

Living roadmap for contributors. See [docs/vision.md](docs/vision.md) for product principles.

---

## Completed

- **MVP Foundation** — CLI, setup wizard, chat, SQLite memory, OpenAI/DeepSeek providers
- **Doctor** — installation and configuration diagnostics (`smith doctor`)
- **Project Context** — deterministic project detection and `.smith/project_context.json`
- **Workspace Intelligence** — multi-project discovery and cached workspace summary
- **Workspace Health** — workstation hygiene scan (`smith health`)
- **Git Intelligence** — read-only repository awareness (`smith git *`)
- **Unified Status Dashboard** — cache-first workstation overview (`smith status`)
- **Sprint 8 — User Context Engine** — deterministic user profile (`smith profile`, `~/.smith/user_context.json`)
- **Sprint 8.1 — User Context Hardening** — working domains, completeness, freshness, confidence reasoning, optional AI inference fallback, enhanced explain

---

## Planned

### Sprint 9 — Planning Engine

**Goal:** Generate implementation plans using existing context.

**Example:**

```bash
smith plan "add oauth login"
```

Planning **must** follow Sprint 9.5 guardrails — not optional.

Uses [`PlanningContext`](smith/models/planning_context.py) from Sprint 8.

---

### Sprint 9.5 — Planning Guardrails Runtime

**Goal:** Prevent hallucinated plans and low-confidence recommendations at runtime.

This sprint is **mandatory** before advanced planning behavior.

See [docs/vision.md](docs/vision.md) principles 4 (Ask Before Assuming) and 7 (Incremental Understanding).

#### Clarification First

If critical information is missing, **do not generate a plan**. Generate questions instead.

**Example:**

```bash
smith plan "add oauth"
```

**Output:**

```text
Missing information:

1. Which provider?
2. Existing authentication?
3. Web only or mobile too?
```

#### Confidence Threshold

Plans should only be generated when:

- confidence exceeds a configurable threshold, **or**
- no critical unknowns remain

#### Unknown Tracking

The planning engine must explicitly track:

- known facts
- assumptions
- open questions

Unknowns should be visible to users via `PlanningContext.unknowns`.

#### Assumption Disclosure

When assumptions are unavoidable, they must be clearly labeled.

#### Explainable Planning

Every generated recommendation should be tied to:

- detected evidence
- project context
- user-provided requirements

---

### Sprint 10 — Context Compression

**Goal:** Reduce context size and token consumption.

**Potential commands:**

```bash
smith context summarize
smith context stats
smith context compact
```

---

### Sprint 11 — Explicit Memory Layer

**Goal:** User-controlled memory.

**Potential commands:**

```bash
smith memory add
smith memory show
smith memory remove
```

---

### Sprint 12 — Cost & Token Analytics

**Goal:** Provide visibility into:

- token usage
- estimated costs
- provider distribution
- context efficiency

---

### Sprint 13 — Multi-Provider Optimization

**Goal:** Route requests intelligently between:

- deterministic workflows
- DeepSeek
- OpenAI

based on complexity and cost.
