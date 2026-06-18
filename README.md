# Smith

<p align="center">
  <a href="https://github.com/YOUR_USERNAME/smith/actions/workflows/ci.yml"><img src="https://github.com/YOUR_USERNAME/smith/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/coverage-%E2%89%A580%25-brightgreen.svg" alt="Coverage ≥80%">
</p>

<p align="center">
  <strong>A benevolent personal AI operator for developers.</strong><br>
  Not a chatbot wrapper — a practical CLI with real tools for code, files, and documents.
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> ·
  <a href="#usage">Usage</a> ·
  <a href="#configuration">Configuration</a> ·
  <a href="#development">Development</a> ·
  <a href="#contributing">Contributing</a>
</p>

---

## About

**Smith** is an open-source, MIT-licensed personal AI assistant inspired by the idea of a capable operator at your side — one that helps you get work done instead of just talking.

Smith ships as a Python CLI with:

- An interactive **chat** session backed by persistent memory
- **Tools** you can run directly or invoke from chat via slash commands
- Support for **OpenAI** and **DeepSeek** as LLM providers
- A **`doctor`** command to diagnose installation and configuration

Smith is built for software development, file organization, document analysis, and everyday productivity.

## Features

| Feature | Description |
|---------|-------------|
| **Chat** | REPL with conversation history stored in SQLite |
| **Context** | Generate structured project context (languages, frameworks, architecture) |
| **Analyze** | Analyze projects using ProjectContext; markdown report, health score, JSON output |
| **Duplicates** | Find duplicate files by SHA-256 hash and report wasted disk space |
| **Organize** | Sort files into category folders (Documents, Images, Code, etc.) |
| **Summarize** | Extract and summarize PDF documents with optional study notes |
| **Doctor** | Validate Python, config, API keys, memory DB, and filesystem access |

## Quick Start

### Requirements

- Python 3.12+
- An API key for [OpenAI](https://platform.openai.com/) and/or [DeepSeek](https://platform.deepseek.com/)

### Install

```bash
git clone https://github.com/YOUR_USERNAME/smith.git
cd smith

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -e ".[dev]"
```

### Configure

Copy the example environment file and add your API key:

```bash
cp .env.example .env
```

Edit `.env` and set at least one of:

```env
OPENAI_API_KEY=sk-...
DEEPSEEK_API_KEY=sk-...
```

Verify your setup:

```bash
smith doctor
smith doctor --test-provider   # optional: test LLM connectivity
```

## Usage

### Workstation tools (Sprint 2)

Every tool is available via **CLI commands** and **chat slash commands**. Successful runs display execution timing (e.g. `Analysis completed in 1.2 seconds.`).

```bash
smith context .
smith analyze .
smith analyze . --structure-only          # offline scan, no LLM
smith analyze . --json                    # JSON health + metadata
smith summarize article.pdf
smith summarize article.pdf --pages 10
smith duplicates ~/Downloads
smith organize ~/Downloads --dry-run
smith organize ~/Downloads
```

```
/context .
/analyze .
/analyze . --structure-only
/summarize article.pdf
/summarize article.pdf --study-notes --pages 10
/duplicates ~/Downloads
/duplicates ~/Downloads --min-size 1024
/organize ~/Downloads --dry-run
/organize ~/Downloads
```

### All commands

```bash
# Interactive chat with slash commands
smith chat

# Generate project context (deterministic, no LLM)
smith context ./my-project

# Analyze a project (markdown report)
smith analyze ./my-project
smith analyze ./my-project --output report.md
smith analyze ./my-project --structure-only
smith analyze ./my-project --json

# Find duplicate files
smith duplicates ~/Downloads
smith duplicates ~/Downloads --min-size 1024

# Organize a folder by file type
smith organize ~/Downloads --dry-run
smith organize ~/Downloads

# Summarize a PDF
smith summarize article.pdf
smith summarize article.pdf --study-notes
smith summarize article.pdf --pages 10

# Diagnostics
smith doctor
smith doctor --test-provider
```

Global flags: `--verbose` / `-v`, `--dry-run` (for destructive commands).

## Configuration

Smith loads settings in this order:

1. Optional `~/.smith/config.toml`
2. `.env` file (project root or `~/.smith/.env`)
3. Environment variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | — |
| `DEEPSEEK_API_KEY` | DeepSeek API key | — |
| `SMITH_LLM_PROVIDER` | Force provider: `openai` or `deepseek` | auto |
| `SMITH_DB_PATH` | SQLite database path | `~/.smith/memory.db` |
| `SMITH_CONFIG_PATH` | Config file path | `~/.smith/config.toml` |
| `SMITH_HOME` | Smith home directory | `~/.smith` |
| `OPENAI_MODEL` | OpenAI model name | `gpt-4o-mini` |
| `DEEPSEEK_MODEL` | DeepSeek model name | `deepseek-chat` |

**Provider selection:** OpenAI is used when `OPENAI_API_KEY` is set; otherwise DeepSeek. Override with `SMITH_LLM_PROVIDER`.

Optional `~/.smith/config.toml`:

```toml
openai_model = "gpt-4o-mini"
deepseek_model = "deepseek-chat"
db_path = "~/.smith/memory.db"
smith_llm_provider = "openai"
```

## Chat Slash Commands

Inside `smith chat`, use slash commands to run tools without leaving the session:

```
/context <path>                         Generate project context snapshot
/duplicates <path> [--min-size N]       Find duplicate files
/organize <path> [--dry-run]            Organize files (asks for confirmation)
/analyze <path> [--structure-only]      Analyze a project
/analyze <path> -o report.md             Save report to file
/summarize <pdf> [--study-notes]        Summarize a PDF
/summarize <pdf> --pages N              Summarize first N pages
/exit                                   Quit
```

Free-form messages go to the LLM with conversation context from memory.

## Safety

Smith treats destructive actions carefully:

- **`smith organize`** shows a plan first and asks for confirmation before moving files
- Use **`--dry-run`** anywhere applicable to preview changes without modifying anything

## Development

```bash
# Lint
ruff check .
ruff format .

# Test (≥80% coverage required)
pytest --cov=smith --cov-fail-under=80
```

CI runs on every push and pull request: lint, format check, tests with coverage, and build.

## Doctor Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All checks pass |
| `1` | Warnings present (e.g. missing config file, connectivity failure) |
| `2` | Critical failures (e.g. no provider, DB or filesystem errors) |

## Contributing

Contributions are welcome! Whether it's a bug report, feature request, or pull request:

1. Fork the repository
2. Create a branch for your change
3. Run `ruff check .` and `pytest --cov=smith --cov-fail-under=80`
4. Open a pull request with a clear description

Issues and discussions are open for questions, ideas, and feedback.

## License

This project is open source and released under the [MIT License](LICENSE).

Copyright (c) 2026 Smith Contributors.

---

<p align="center">
  Made with care by the Smith community.
</p>
