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
- **Sprint 9 — Guided Planning Engine** — context-aware planning (`smith plan`, clarification, status integration)
- **Sprint 9.1 — Guided Planning Hardening** — evidence-first knowns, deterministic confidence, assumption budget, compact LLM prompts, enhanced explain
- **Sprint 9.2 — Context Gap Analysis** — universal dimension-based gap detection replaces domain-template planning; interactive `smith plan answer` loop; severity-based readiness
- **Sprint 10 — Grounded Assistant Layer** — `ContextOrchestrator`, capability registry, repository resolution, grounding guardrails, terminal UX phases, in-memory session
- **Sprint 10.5 — Investigative Context Acquisition & Repository Intelligence** — depth-aware filesystem investigation, `RepositoryKnowledge`, architecture/quality/risk detectors, themed terminal UX, structured review responses, follow-up knowledge reuse

---

## Planned

### Future — Decision Context

Store explicit user decisions and planning answers so future plans become
progressively more accurate without repeatedly asking the same questions.

Potential scope:

- Persist planning answers alongside user profile
- Reuse prior decisions in gap analysis
- Reduce repeated clarification across sessions

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
- context gaps (universal dimensions)
- assumptions
- open questions

Gaps should be visible to users via `PlanningContext.gaps` and `smith plan explain`.

#### Assumption Disclosure

When assumptions are unavoidable, they must be clearly labeled.

#### Explainable Planning

Every generated recommendation should be tied to:

- detected evidence
- project context
- user-provided requirements

---

### Sprint 11 — Context Compression

**Goal:** Reduce context size and token consumption.

**Potential commands:**

```bash
smith context summarize
smith context stats
smith context compact
```

---

### Sprint 12 — Memory Layer

**Goal:** User-controlled memory.

**Potential commands:**

```bash
smith memory add
smith memory show
smith memory remove
```

---

### Sprint 13 — Token Economics

**Goal:** Token budgeting, accounting, and pruning — visibility into usage, estimated costs, provider distribution, and context efficiency.

---

### Sprint 14 — Decision Context

**Goal:** Store explicit user decisions and planning answers so future plans become progressively more accurate without repeatedly asking the same questions.

Potential scope:

- Persist planning answers alongside user profile
- Reuse prior decisions in gap analysis
- Reduce repeated clarification across sessions

---

### Sprint 15 — Repository Intelligence Expansion

**Goal:** Extend deterministic repository intelligence — richer dependency graphs, cross-module coupling analysis, and deeper architecture pattern libraries.

Builds on Sprint 10.5 `RepositoryKnowledge` and investigative acquisition.

---

### Sprint 16 — Semantic Retrieval (RAG)

**Goal:** Optional retrieval-augmented generation for large codebases.

**Explicitly deferred** until repository grounding (Sprint 10) and repository intelligence (Sprint 10.5/15) are mature. RAG is not a substitute for evidence-first orchestration.

---

### Sprint 17 — Cross-Repository Knowledge Graph

**Goal:** Connect repository knowledge across a workspace — shared dependencies, patterns, and comparative insights without autonomous agents.
