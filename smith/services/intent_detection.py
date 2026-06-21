"""Lightweight reference extraction and follow-up detection for grounded chat."""

from __future__ import annotations

import re
from pathlib import Path

from smith.models.assistant import AssistantSession

_PATH_PATTERN = re.compile(
    r"(?:"
    r"(?:~[\w./-]+)|"
    r"(?:/[\w./-]+)|"
    r"(?:\.\./[\w./-]+)|"
    r"(?:\./[\w./-]+)|"
    r"(?:[\w.-]+\.(?:py|ts|tsx|js|jsx|go|rs|java|md|json|yaml|yml|toml))"
    r")"
)
_QUOTED_NAME_PATTERN = re.compile(r"""['"]([A-Za-z][\w-]{1,})['"]""")
_BARE_NAME_PATTERN = re.compile(r"\b([A-Za-z][\w-]{1,})\b")
_PASCAL_CASE_PATTERN = re.compile(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b")
_FOLLOW_UP_MAX_WORDS = 8
_FOLLOW_UP_SIGNALS = (
    "what about",
    "and the",
    "how about",
    "what is",
    "what's",
    "does it",
    "tell me more",
    "also",
)
_LOCATION_SCOPE_PATTERNS = (
    "one directory above",
    "one folder above",
    "one level above",
    "parent folder",
    "parent directory",
    "sibling project",
    "sibling folder",
    "sibling repository",
    "next to this",
    "same folder as",
    "folder above",
    "directory above",
)
_ANALYTICAL_TRIGGERS = (
    "analyze",
    "review",
    "summarize",
    "compare",
    "architecture",
    "improve",
    "suggest",
)


def extract_references(message: str) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()

    for match in _QUOTED_NAME_PATTERN.finditer(message):
        name = match.group(1)
        if name not in seen:
            seen.add(name)
            refs.append(name)

    for match in _PATH_PATTERN.finditer(message):
        token = match.group(0)
        if token not in seen:
            seen.add(token)
            refs.append(token)

    analytical = any(trigger in message.lower() for trigger in _ANALYTICAL_TRIGGERS)
    if analytical:
        for match in _PASCAL_CASE_PATTERN.finditer(message):
            name = match.group(1)
            if name.lower() in REPOSITORY_NAME_STOP_WORDS or name in seen:
                continue
            seen.add(name)
            refs.append(name)

    for match in _BARE_NAME_PATTERN.finditer(message):
        name = match.group(1)
        if name.lower() in REPOSITORY_NAME_STOP_WORDS or name in seen:
            continue
        if any(name in r for r in refs):
            continue
        seen.add(name)
        refs.append(name)
    return refs


def extract_location_scope(message: str, cwd: Path) -> Path | None:
    text = message.lower()
    if any(pattern in text for pattern in _LOCATION_SCOPE_PATTERNS):
        return cwd.expanduser().resolve().parent
    if "sibling" in text and "sibling" not in REPOSITORY_NAME_STOP_WORDS:
        return cwd.expanduser().resolve().parent
    return None


def has_location_hint(message: str, cwd: Path) -> bool:
    return extract_location_scope(message, cwd) is not None


def is_follow_up(message: str, session: AssistantSession | None) -> bool:
    if session is None or not session.last_capability_id:
        return False
    text = message.strip().lower()
    words = text.split()
    if len(words) > _FOLLOW_UP_MAX_WORDS:
        return False
    if any(signal in text for signal in _FOLLOW_UP_SIGNALS):
        return True
    if session.analysis_target and not extract_references(message):
        return len(words) <= 6
    return False


def is_knowledge_follow_up(message: str, session: AssistantSession | None) -> bool:
    if session is None or not session.repository_knowledge_by_path:
        return False
    if not is_follow_up(message, session):
        return False
    text = message.lower()
    knowledge_triggers = (
        "framework",
        "stack",
        "technology",
        "test",
        "risk",
        "concern",
        "architecture",
        "module",
    )
    return any(trigger in text for trigger in knowledge_triggers)


def extract_file_reference(message: str, cwd: Path) -> Path | None:
    for ref in extract_references(message):
        candidate = Path(ref)
        if candidate.suffix and not ref.startswith("/") and ".." not in ref and not ref.startswith("~"):
            path = (cwd / candidate).resolve()
            if path.is_file():
                return path
    return None


REPOSITORY_NAME_STOP_WORDS = frozenset(
    {
        "analyze",
        "review",
        "explain",
        "compare",
        "plan",
        "summarize",
        "what",
        "does",
        "this",
        "that",
        "the",
        "and",
        "for",
        "with",
        "about",
        "project",
        "repository",
        "repo",
        "code",
        "file",
        "structure",
        "architecture",
        "stack",
        "overview",
        "tell",
        "show",
        "me",
        "how",
        "should",
        "work",
        "next",
        "steps",
        "roadmap",
        "difference",
        "between",
        "changed",
        "located",
        "directory",
        "above",
        "below",
        "sibling",
        "suggest",
        "improvements",
        "improvement",
        "propose",
        "one",
        "do",
        "not",
        "modify",
        "anything",
        "hello",
        "something",
        "analise",
        "analisar",
        "projeto",
        "proponha",
        "melhorias",
        "melhoria",
        "melhor",
        "sugerir",
        "sugest",
    }
)
