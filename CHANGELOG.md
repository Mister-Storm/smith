# Changelog

All notable changes to Smith are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Context Gap Analysis** (Sprint 9.2):
  - Universal `PlanningDimension` gap detection replaces domain-template planning
  - `ContextGap`, `PlanningDecision`, severity-based readiness
  - Interactive loop: `smith plan answer`, session-scoped decisions (no persistence yet)
  - Optional `--prioritize` LLM re-ranking of existing gaps only
  - Enhanced explain output: Detected Gaps + Explicit Decisions
  - Decision Context deferred to future ROADMAP sprint
- **User Context Engine** (Sprint 8 + 8.1):
  - CLI: `smith profile show`, `refresh`, `explain`, `set-interest`, `remove-interest`, `set-goal`, `remove-goal`
  - Global profile at `~/.smith/user_context.json` with derived + user override merge
  - Working domains, profile completeness, confidence reasoning, freshness helpers
  - Optional AI-assisted context inference (`profile refresh --infer`) when deterministic gaps exist
  - `PlanningContext` model with `gaps` for Sprint 9.2
  - User Context section in `smith status`
  - Vision User Understanding section; ROADMAP renumbered (Sprints 9–13)
- **Guided Planning Engine** (Sprint 9 + 9.1):
  - CLI: `smith plan`, `plan-status`, `plan-refresh`, `plan explain`, `plan answer`
  - `PlanningService` with evidence-first knowns, dimension gap analysis, clarification questions
  - Deterministic confidence (40/30/20/10 context weights), assumption budget (`MAX_ASSUMPTIONS=3`)
  - Plans generated only when `can_generate_plan()` passes; compact LLM prompts (<1500 tokens)
  - Chat: `/plan`, `/plan answer`, `/plan-status`, `/plan-refresh`
  - Planning Readiness + Planning Philosophy in `smith status`
  - Vision Guided Planning + Core Planning Principles; ROADMAP Sprint 9/9.1 completed

### Added (prior)

- **Product governance:**
  - [docs/vision.md](docs/vision.md) — mission and seven core principles (AI Last, Context Is a Product, Token Economy, Ask Before Assuming, Human Control, Explainability, Incremental Understanding)
  - [ROADMAP.md](ROADMAP.md) — completed milestones and planned Sprints 8–12 including mandatory Sprint 8.5 Planning Guardrails
- **Unified Status Dashboard** (`smith status`):
  - Cache-first aggregation from project context, workspace context, workstation health cache, doctor, and git intelligence
  - Environment, cache freshness, recommendations (deduped); no LLM calls; target under 2 seconds
  - Workstation health cache (`.smith/workstation_health.json`) written after `smith health`
- **`.smith` git hygiene:** `.smith/*` + `!.smith/.gitkeep` pattern in repo `.gitignore` and Smith runtime helper

### Added (prior)

- **Workspace Intelligence** (multi-project aggregation):
  - CLI: `smith workspace`, `workspace-health`, `refresh-workspace-context`, `workspace-context`
  - Chat: `/workspace`, `/workspace-health`, `/workspace-context`, `/refresh-workspace-context`
  - `WorkspaceIntelligenceService` with project discovery, activity ranking, health checks, and cached `.smith/workspace_context.json` (`schema_version: 1`)
  - Models: `WorkspaceProject`, `WorkspaceSummary`, `WorkspaceHealth`
  - `.smith/` gitignore helper applied on project and workspace context save (never creates `.gitignore`)
  - `GitIntelligenceService.get_last_commit_date()` and safe try_* helpers for aggregation
  - Unit and integration tests for discovery, validation, gitignore, CLI, and chat commands

## [0.1.0] - 2026-06-20

### Added

- Initial Smith CLI with setup wizard, doctor diagnostics, and version command
- Project analysis (`smith analyze`) with structure-only and JSON output modes
- PDF summarization (`smith summarize`) with optional study notes and page limits
- Duplicate file detection (`smith duplicates`) and download organization (`smith organize`)
- SQLite-backed conversation memory with persistent sessions
- OpenAI and DeepSeek LLM provider support with environment-based API keys
- Interactive chat assistant (`smith chat`) with slash commands and startup banner ([#1](https://github.com/Mister-Storm/smith/pull/1))
- Project context system: `smith context`, `smith refresh-context`, and `.smith/project_context.json` ([#3](https://github.com/Mister-Storm/smith/pull/3))
- Deterministic project detection (language, framework, CI/CD, Docker, test layout)
- Chat integration for project context (`/context`, `/refresh-context`)
- Workstation health scan (`smith health`) with correlated findings and read-only recommendations
- `smith model` command for DeepSeek V4 model selection (Flash / Pro) ([#4](https://github.com/Mister-Storm/smith/pull/4))
- Redesigned chat startup banner with provider, model, and session status
- **Git Intelligence** (read-only repository awareness):
  - CLI: `smith git summary`, `changes`, `commit-message`, `release-notes`, `health`
  - Chat: `/git-summary`, `/git-changes`, `/commit-message`, `/release-notes`, `/git-health`
  - `GitIntelligenceService` with git CLI integration (no commits, pushes, or mutations)
  - Models: `RepositoryStatus`, `ChangeSummary`, `GitHealthReport`, `DevelopmentAssessment`
  - Conventional Commit suggestions and grouped release notes (Features, Bug Fixes, Documentation, Testing, Maintenance)
  - `.smith/**` artifact filtering and specialized area classification (Git, Health, Context)
  - Informational Git Health section in `smith health` (no scoring impact)
  - Slash command registry and dispatcher (`smith/services/slash_commands.py`)
  - Unit and integration test coverage for git commands, chat slash commands, banner, and workstation health Git section
  - README Git Intelligence section

### Changed

- Chat slash command dispatch moved from if-chain to registry/dispatcher pattern

### Fixed

- Chat startup banner rendering ([#2](https://github.com/Mister-Storm/smith/pull/2))
