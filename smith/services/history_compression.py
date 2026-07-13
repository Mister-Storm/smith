"""Session history compression.

Reduces token usage by summarizing older messages when a session grows long.
"""

from __future__ import annotations

import logging

from smith.llm.base import LLMProvider
from smith.memory.service import MemoryService

logger = logging.getLogger(__name__)

_COMPRESSION_THRESHOLD = 30  # messages before compression triggers
_KEEP_LATEST = 10  # most recent messages to keep intact


def compress_session_history(
    session_id: str,
    memory: MemoryService,
    llm: LLMProvider,
    *,
    threshold: int = _COMPRESSION_THRESHOLD,
    keep_latest: int = _KEEP_LATEST,
) -> bool:
    """Compress old session messages using the LLM.

    Returns True if compression was performed.
    """
    count = memory.count_session_messages(session_id)
    if count < threshold:
        return False

    all_messages = memory.get_all_session_messages(session_id)
    if len(all_messages) <= keep_latest:
        return False

    old_messages = all_messages[:-keep_latest]

    transcript_parts: list[str] = []
    for role, content in old_messages:
        label = "User" if role == "user" else "Assistant"
        transcript_parts.append(f"{label}: {content[:200]}")

    summary_prompt = (
        "Summarize the following conversation history concisely. "
        "Capture key facts, decisions, goals, and context. "
        "Write in English or Portuguese as appropriate.\n\n" + "\n".join(transcript_parts)
    )

    try:
        summary = llm.generate(
            summary_prompt,
            system="You are a helpful assistant that summarizes conversations.",
        )
    except Exception as exc:
        logger.warning("Session compression failed for %s: %s", session_id, exc)
        return False

    memory.replace_old_messages(
        session_id,
        keep_count=keep_latest,
        summary_content=summary,
    )

    logger.info(
        "Session %s compressed: %d messages -> 1 summary + %d recent",
        session_id,
        len(old_messages),
        keep_latest,
    )
    return True
