"""Reference extraction, path resolution, and follow-up detection for grounded chat."""

from __future__ import annotations

import re
from collections.abc import Callable
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
_FOLDER_LABEL_PATTERN = re.compile(
    r"\b(?:folder|directory|pasta|diret[óo]rio)\s+([~./\w-]+)",
    re.IGNORECASE,
)
_IN_PATH_PATTERN = re.compile(
    r"\b(?:in|em|inside|within|under)\s+([~./][\w./-]+|\./[\w./-]+|\.\./[\w./-]+)",
    re.IGNORECASE,
)
_THIS_LOCATION_PATTERN = re.compile(
    r"\b(?:this|current|esta|este|essa|esse|desta|deste|desse|dessa)\s+"
    r"(?:folder|directory|pasta|diret[óo]rio|project|projeto|repo|repository)\b",
    re.IGNORECASE,
)

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
    "e quanto",
    "e os",
    "e as",
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
    "pasta acima",
    "diretório acima",
    "diretorio acima",
    "pasta ao lado",
    "projeto ao lado",
    "um diretório acima",
    "uma pasta acima",
)
_ANALYTICAL_TRIGGERS = (
    "analyze",
    "analise",
    "analisar",
    "review",
    "summarize",
    "compare",
    "architecture",
    "improve",
    "suggest",
)

_CONTEXT_SIGNALS = frozenset({"context", "contexto"})
_CONTEXT_ACTIONS = frozenset(
    {
        "identify",
        "detect",
        "inspect",
        "determine",
        "discover",
        "identifique",
        "identificar",
        "detectar",
        "inspecionar",
        "descobrir",
        "determinar",
    }
)
_CONTEXT_LOCATION_SIGNALS = frozenset(
    {
        "folder",
        "directory",
        "pasta",
        "diretório",
        "diretorio",
        "project",
        "projeto",
        "repo",
        "repository",
        "repositório",
        "repositorio",
        "workspace",
    }
)
_CONTEXT_TYPE_SIGNALS = (
    "what kind",
    "what type",
    "que tipo",
    "qual tipo",
    "tipo de",
    "kind of project",
    "type of project",
)

REPOSITORY_NAME_STOP_WORDS = frozenset(
    {
        "analyze",
        "analise",
        "analisar",
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
        "projeto",
        "proponha",
        "melhorias",
        "melhoria",
        "melhor",
        "sugerir",
        "sugest",
        "identify",
        "identifique",
        "identificar",
        "detect",
        "detectar",
        "context",
        "contexto",
        "folder",
        "pasta",
        "diretório",
        "diretorio",
        "kind",
        "type",
        "tipo",
        "qual",
        "que",
        "need",
        "want",
        "please",
        "can",
        "you",
        "could",
        "would",
        "through",
        "desta",
        "deste",
        "desse",
        "dessa",
        "via",
        "using",
        "chat",
    }
)


def is_context_detection_intent(message: str) -> bool:
    """True when the user wants project/folder context identified (EN or PT)."""
    text = message.lower()
    words = set(re.findall(r"[a-záàâãéêíóôõúç]+", text))
    has_context = bool(words & _CONTEXT_SIGNALS) or "project context" in text
    has_action = bool(words & _CONTEXT_ACTIONS)
    has_location = bool(words & _CONTEXT_LOCATION_SIGNALS)
    has_type_question = any(signal in text for signal in _CONTEXT_TYPE_SIGNALS)
    return has_context and (has_action or has_location or has_type_question)


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

    for match in _FOLDER_LABEL_PATTERN.finditer(message):
        token = match.group(1)
        if token not in seen:
            seen.add(token)
            refs.append(token)

    for match in _IN_PATH_PATTERN.finditer(message):
        token = match.group(1)
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


def extract_target_path(message: str, cwd: Path) -> Path | None:
    """Resolve the folder the user is referring to, when possible."""
    root = cwd.expanduser().resolve()

    if _THIS_LOCATION_PATTERN.search(message):
        return root

    for ref in extract_references(message):
        candidate = Path(ref).expanduser()
        if candidate.is_absolute() and candidate.is_dir():
            return candidate.resolve()
        resolved = (root / candidate).resolve()
        if resolved.is_dir():
            return resolved
        if ref.startswith((".", "/")) or ref.startswith("~"):
            parent = resolved.parent
            if parent.is_dir() and not resolved.exists():
                return parent

    scope = extract_location_scope(message, root)
    if scope is not None:
        return scope

    return None


def extract_location_scope(message: str, cwd: Path) -> Path | None:
    text = message.lower()
    if any(pattern in text for pattern in _LOCATION_SCOPE_PATTERNS):
        return cwd.expanduser().resolve().parent
    if "sibling" in text or "ao lado" in text:
        return cwd.expanduser().resolve().parent
    return None


def has_location_hint(message: str, cwd: Path) -> bool:
    return extract_location_scope(message, cwd) is not None or bool(
        _THIS_LOCATION_PATTERN.search(message)
    )


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
        is_relative_file = (
            candidate.suffix
            and not ref.startswith("/")
            and ".." not in ref
            and not ref.startswith("~")
        )
        if is_relative_file:
            path = (cwd / candidate).resolve()
            if path.is_file():
                return path
    return None


IntentMatcher = Callable[[str], bool]
