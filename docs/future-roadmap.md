# Smith Future Roadmap

This document tracks ideas under consideration. Nothing here is committed to a release.

## Sprint 3 — Project Context (implemented)

```bash
smith context .
smith analyze . --json
```

**Delivered:**

- `ProjectContext` as the canonical project snapshot (deterministic, no LLM)
- SQLite persistence in `project_contexts`
- `AnalyzeProjectTool` v2 (health score, architecture observations, JSON output)
- Chat `/context` slash command

## Future ideas

- **CodingAgent** — consume `ProjectContext` for targeted code changes
- **Refactoring Assistant** — layer-aware refactors guided by context
- **Architecture Review** — deeper structural reports from persisted context

**Status:** Backlog only.
