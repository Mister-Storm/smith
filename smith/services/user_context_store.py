"""Persistence for ~/.smith/user_context.json."""

from __future__ import annotations

import logging
from pathlib import Path

from smith.core.config import get_smith_home
from smith.models.user_context import UserContextDocument

logger = logging.getLogger(__name__)

USER_CONTEXT_FILE = "user_context.json"


def user_context_path() -> Path:
    return get_smith_home() / USER_CONTEXT_FILE


class UserContextStore:
    @staticmethod
    def exists() -> bool:
        return user_context_path().is_file()

    @staticmethod
    def load() -> UserContextDocument:
        path = user_context_path()
        if not path.is_file():
            return UserContextDocument.empty()
        try:
            return UserContextDocument.from_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            logger.warning("Failed to load user context from %s: %s", path, exc)
            return UserContextDocument.empty()

    @staticmethod
    def save(document: UserContextDocument) -> Path:
        path = user_context_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(document.to_json(), encoding="utf-8")
        logger.info("Saved user context to %s", path)
        return path
