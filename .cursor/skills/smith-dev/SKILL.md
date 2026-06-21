---
name: smith-dev
description: Smith local development workflow — venv setup, lint, test, and CLI smoke checks. Use when setting up the dev environment, running tests, fixing CI, or validating changes before a PR.
---

# Smith Development

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # add OPENAI_API_KEY or DEEPSEEK_API_KEY
smith setup && smith doctor
```

## Quality gate (run before PR)

```bash
ruff check . && ruff format .
pytest --cov=smith --cov-fail-under=80
```

## Targeted tests

```bash
pytest tests/unit/test_<module>.py -q          # single module
pytest tests/integration/test_cli.py -q       # CLI integration
```

## Manual smoke

```bash
smith chat
smith context .
smith status
smith plan "build a personal knowledge base"
```

## Project layout

- `smith/cli/` — Typer entrypoints only
- `smith/services/` — business logic
- `smith/tools/` — filesystem / side effects
- `tests/helpers/` — shared fixtures (`workspace_fixture`, `git_repo`, `buildtwin_fixture`)

## Config paths

- User config: `~/.smith/config.toml`
- Project cache: `.smith/project_context.json` (gitignored)
- Memory DB: `~/.smith/memory.db`

Never commit `.env`, `*.db`, or `.smith/` artifacts.
