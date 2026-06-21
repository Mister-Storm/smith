<p align="center">
  <img src="docs/assets/logo/smith.png" alt="Smith logo" width="120">
</p>

<h1 align="center">SMITH</h1>

<p align="center">
  <strong>Organize Complexity</strong><br>
  Personal AI Operator for Developers
</p>

<p align="center">
  <a href="https://github.com/Mister-Storm/smith/actions/workflows/ci.yml"><img src="https://github.com/Mister-Storm/smith/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/coverage-%E2%89%A580%25-brightgreen.svg" alt="Coverage ≥80%">
  <img src="https://img.shields.io/badge/PyPI-smith--ai-blue.svg" alt="PyPI">
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> ·
  <a href="#demo">Demo</a> ·
  <a href="#features">Features</a> ·
  <a href="#usage">Usage</a> ·
  <a href="#roadmap">Roadmap</a> ·
  <a href="CHANGELOG.md">Changelog</a> ·
  <a href="#contributing">Contributing</a>
</p>

---

## Overview

**Smith** is an open-source AI operator designed to help developers manage projects, documents, files, and daily workstation tasks using modern LLMs such as [DeepSeek](https://platform.deepseek.com/) and [OpenAI](https://platform.openai.com/).

It combines:

- **AI chat** with persistent memory
- **Project analysis** and architecture intelligence
- **PDF summarization**
- **Duplicate file detection**
- **Workstation automation**

All from a **terminal-first** experience — no web UI required.

---

## Quick Start

**Requirements:** Python 3.12+ · OpenAI and/or DeepSeek API key

```bash
pipx install smith-ai

smith setup
smith doctor
smith chat
smith context .
```

<details>
<summary>Install from source (development)</summary>

```bash
git clone https://github.com/Mister-Storm/smith.git
cd smith
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
smith setup
```

</details>

---

## Demo

![Smith Demo](docs/assets/demo.gif)

> **Note:** Demo GIF will be added after Sprint UX. See [roadmap](#roadmap).

---

## Features

| Feature | Status |
|---------|--------|
| Chat | ✅ |
| Project Analysis | ✅ |
| Project Context | ✅ |
| PDF Summarization | ✅ |
| Duplicate Detection | ✅ |
| Downloads Organization | ✅ |
| Workstation Health | ✅ |
| Local Memory | ✅ |
| Setup Wizard | ✅ |
| Rich Terminal UI | ✅ |
| PyPI Distribution | 🚧 |

---

## Screenshots

Placeholders for upcoming CLI captures.

### Chat

![Chat](docs/assets/chat.png)

### Analyze Project

![Analyze](docs/assets/analyze.png)

### Doctor

![Doctor](docs/assets/doctor.png)

---

## Usage

Every tool works as a **CLI command** and a **chat slash command**. Runs show execution time and a suggested next step.

```bash
smith help
smith version
smith context .
smith refresh-context .
smith analyze . --structure-only
smith analyze . --json
smith summarize document.pdf --pages 10
smith duplicates ~/Downloads
smith organize ~/Downloads --dry-run
smith doctor --test-provider
```

**Chat slash commands**

```
/context              /refresh-context
/analyze . --structure-only
/summarize doc.pdf    /duplicates ~/Downloads
/organize ~/Downloads --dry-run
/exit
```

Global flags: `--verbose` / `-v` · `--dry-run`

---

## Project Context

Smith can inspect your workspace once and reuse that metadata in chat.

```bash
smith context .                  # analyze and save
smith refresh-context .          # force re-analysis
smith context . --output ctx.json
smith context . --debug          # show detection trace (troubleshooting)
```

**Storage:** `.smith/project_context.json` in the project directory (human-readable JSON, no database, no embeddings).

**Git hygiene:** All files under `.smith/` are local-only artifacts. Smith appends `.smith/*` and `!.smith/.gitkeep` to your repository `.gitignore` when one exists (never creates `.gitignore`). Do not commit generated Smith context to version control.

**What it detects:** language, framework, build system, databases, infrastructure, CI/CD, and modules — all via deterministic file inspection (no LLM tokens).

**Chat integration:** When you run `smith chat` inside a project, Smith loads `.smith/project_context.json` and injects a compact context block into the system prompt (max 500 characters). Use `/context` to view loaded context and `/refresh-context` to rebuild it.

---

## Workstation Health

Smith can scan your workstation for hygiene issues and produce **read-only recommendations** — it never modifies or deletes files.

```bash
smith health                              # scan Downloads, Desktop, Documents
smith health --paths ~/Downloads          # scan specific directories
smith health --json                       # machine-readable report
```

| Command | Checks |
|---------|--------|
| `smith doctor` | Smith installation (Python, API keys, memory DB) |
| `smith health` | Workstation hygiene (clutter, caches, manifests, disk) |

**Chat:** `/health [path]` runs the same scan inside chat.

Correlated findings (e.g. low disk + large caches) are grouped into actionable insights with safe next steps like `smith organize --dry-run` or `smith duplicates`.

When run inside a Git repository, `smith health` also includes an informational **Git Health** section (branch, modified/untracked counts, development assessment). This does not affect the health score.

After each scan, Smith caches a condensed summary to `.smith/workstation_health.json` for use by `smith status`.

---

## Status Dashboard

A single cache-first workstation overview — no rescans, no AI calls.

```bash
smith status [path]
```

| Section | Source |
|---------|--------|
| Environment | Provider, model, memory DB, config path |
| Cache Freshness | Ages for project, workspace, and health caches |
| Workstation Health | Cached `smith health` summary |
| Workspace Summary | Cached `.smith/workspace_context.json` |
| Current Project | Cached `.smith/project_context.json` |
| Git Status | Live git read (branch, modified, untracked, suggested commit) |
| Recommendations | Deduped hints from health, workspace, git, and cache state |

Stale or missing caches suggest `smith refresh-context .`, `smith workspace .`, or `smith health`.

See [docs/vision.md](docs/vision.md) and [ROADMAP.md](ROADMAP.md) for product direction.

---

## Git Intelligence

Smith understands your repository state — what changed, what you are working on, and how to communicate those changes. **All Git Intelligence commands are strictly read-only.** Smith never creates commits, pushes, pulls, rebases, or modifies your repository.

```bash
smith git summary              # status, top areas, suggested commit
smith git changes              # human-readable explanation of changes
smith git commit-message       # up to 3 Conventional Commit suggestions
smith git release-notes        # release notes from last 20 commits
smith git health               # compact repository health overview
```

| Command | Purpose |
|---------|---------|
| `smith git summary` | Branch, file counts, top changed areas, assessment, suggested commit |
| `smith git changes` | List changed files and heuristic summary |
| `smith git commit-message` | Conventional Commit suggestions (`feat`, `fix`, `refactor`, etc.) |
| `smith git release-notes` | Grouped release notes (Features, Bug Fixes, Documentation, Testing, Maintenance) |
| `smith git health` | Repository overview |

**Development assessment** (informational only):

| Assessment | Meaning |
|------------|---------|
| Clean | No modified, untracked, or staged files |
| Ready for Commit | Staged changes present, few unstaged modifications |
| Work in Progress | Many unstaged or untracked changes |

Smith-generated artifacts under `.smith/` are automatically ignored when analyzing changes, even if not in `.gitignore`.

**Chat:** `/git-summary`, `/git-changes`, `/commit-message`, `/release-notes`, `/git-health`

---

## Workspace Intelligence

Smith can discover multiple projects under a directory, aggregate per-project context and git activity, and cache a workspace summary for chat.

```bash
smith workspace [path]                    # live multi-project overview
smith workspace-health [path]             # README / CI / tests / stale counts
smith refresh-workspace-context [path]    # write .smith/workspace_context.json
smith workspace-context [path]            # show cached workspace summary
```

| Command | Purpose |
|---------|---------|
| `smith workspace` | Discover projects (`.git`, `pyproject.toml`, `package.json`, etc.), rank by activity, show languages and frameworks |
| `smith workspace-health` | Informational counts — missing README, CI, tests, stale repos |
| `smith refresh-workspace-context` | Build summary, save cache (`schema_version: 1`), ensure `.smith/` in `.gitignore` |
| `smith workspace-context` | Load cached summary from `.smith/workspace_context.json` |

Discovery scans up to **3 levels deep** by default (`--max-depth`), skips common vendor/build dirs, and stops after **100 projects** with a warning. A directory with one project still works but shows guidance to run `smith context`.

**Chat:** `/workspace`, `/workspace-health`, `/workspace-context`, `/refresh-workspace-context`

---

## Philosophy

Smith is built on a few simple ideas:

| Principle | What it means |
|-----------|---------------|
| **Terminal first** | Your shell is the control plane. No browser, no dashboard. |
| **Provider agnostic** | OpenAI and DeepSeek today; architecture ready for more. |
| **Developer focused** | Project analysis, context, and file tools — not generic chat. |
| **Local configuration** | Settings in `~/.smith/`; API keys in environment variables only. |
| **Open source** | MIT licensed. Inspect, fork, contribute. |
| **Automation over complexity** | Real tools with deterministic output, not agent orchestration theater. |

---

## Configuration

Settings load in order: `~/.smith/config.toml` → `.env` → environment variables.

API keys **never** go in `config.toml`. Use `smith setup` or `source ~/.smith/env.sh`.

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` / `DEEPSEEK_API_KEY` | LLM credentials (required) |
| `SMITH_LLM_PROVIDER` | Force `openai` or `deepseek` |
| `SMITH_DB_PATH` | SQLite memory path (default `~/.smith/memory.db`) |
| `OPENAI_MODEL` / `DEEPSEEK_MODEL` | Model names (`deepseek-v4-flash` or `deepseek-v4-pro`) |

<details>
<summary>Example config.toml (non-secret settings only)</summary>

```toml
smith_llm_provider = "openai"
openai_model = "gpt-4o-mini"
deepseek_model = "deepseek-v4-flash"
db_path = "~/.smith/memory.db"
```

</details>

---

## Roadmap

Product direction: [docs/vision.md](docs/vision.md) · Sprint plan: [ROADMAP.md](ROADMAP.md)

### Completed

- Chat with slash commands and SQLite memory
- Analyze Project (health score, JSON output, architecture observations)
- Project Context (`smith context`)
- Git Intelligence (read-only repository awareness)
- Workspace Intelligence (multi-project discovery and cached context)
- Unified Status Dashboard (`smith status`)
- Summarize PDF
- Duplicate Detection
- Organize Downloads
- Rich Terminal UI (banner, tables, markdown)
- Setup Wizard (`smith setup`, `smith help`, `smith version`)

### In Progress

- PyPI distribution (`pipx install smith-ai`)
- README demo GIF and screenshots

### Future

See [ROADMAP.md](ROADMAP.md) for planned sprints (Planning Engine, Context Compression, Memory Layer, Token Analytics, Multi-Provider Optimization).

See [docs/future-roadmap.md](docs/future-roadmap.md) for archived ideas.

---

## Brand Assets

Smith has an official visual identity. Assets live under [`docs/assets/logo/`](docs/assets/logo/):

| Asset | Path | Use |
|-------|------|-----|
| Primary logo | `docs/assets/logo/smith.png` | README hero, docs |
| Dark mode | `smith-dark.png` | *planned* |
| Favicon | `favicon.ico` | *planned* |
| Terminal icon | `smith-icon.png` | *planned* |

The logo appears once in this README (hero). See [`docs/assets/logo/README.md`](docs/assets/logo/README.md) for the full asset layout.

---

## Development

```bash
ruff check . && ruff format .
pytest --cov=smith --cov-fail-under=80
```

**Doctor exit codes:** `0` healthy · `1` warnings · `2` critical

**Releasing to PyPI:** GitHub Release → publish workflow → `pipx install smith-ai`

---

## Contributing

Contributions welcome — bugs, ideas, and pull requests.

1. Fork the repo
2. Create a branch
3. Add a bullet under `[Unreleased]` in [CHANGELOG.md](CHANGELOG.md) (`Added`, `Changed`, `Fixed`, etc.). One line per user-visible change; link PR numbers when helpful.
4. Run lint and tests
5. Open a PR with a clear description

When releasing a new version, rename the `[Unreleased]` section to `[X.Y.Z] - YYYY-MM-DD`, bump the version in `pyproject.toml`, and add a fresh `[Unreleased]` section at the top.

---

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 Smith Contributors.

<p align="center">
  <sub>Smith — organize complexity.</sub>
</p>
