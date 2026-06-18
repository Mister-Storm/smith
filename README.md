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

**What it detects:** language, framework, build system, databases, infrastructure, CI/CD, and modules — all via deterministic file inspection (no LLM tokens).

**Chat integration:** When you run `smith chat` inside a project, Smith loads `.smith/project_context.json` and injects a compact context block into the system prompt (max 500 characters). Use `/context` to view loaded context and `/refresh-context` to rebuild it.

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
| `OPENAI_MODEL` / `DEEPSEEK_MODEL` | Model names |

<details>
<summary>Example config.toml (non-secret settings only)</summary>

```toml
smith_llm_provider = "openai"
openai_model = "gpt-4o-mini"
deepseek_model = "deepseek-chat"
db_path = "~/.smith/memory.db"
```

</details>

---

## Roadmap

### Completed

- Chat with slash commands and SQLite memory
- Analyze Project (health score, JSON output, architecture observations)
- Project Context (`smith context`)
- Summarize PDF
- Duplicate Detection
- Organize Downloads
- Rich Terminal UI (banner, tables, markdown)
- Setup Wizard (`smith setup`, `smith help`, `smith version`)

### In Progress

- PyPI distribution (`pipx install smith-ai`)
- README demo GIF and screenshots

### Future

- Workspace automation
- Additional LLM providers
- Coding agent and refactoring assistant (via `ProjectContext`)
- Architecture review reports

See [docs/future-roadmap.md](docs/future-roadmap.md) for details.

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
3. Run lint and tests
4. Open a PR with a clear description

---

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 Smith Contributors.

<p align="center">
  <sub>Smith — organize complexity.</sub>
</p>
