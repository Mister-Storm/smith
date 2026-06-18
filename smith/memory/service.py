import uuid
from datetime import UTC, datetime
from pathlib import Path

from smith.memory.db import get_connection


class MemoryService:
    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._conn = get_connection(self._db_path)

    @property
    def db_path(self) -> Path:
        return self._db_path

    def start_session(self) -> str:
        return str(uuid.uuid4())

    def add_message(self, session_id: str, role: str, content: str) -> None:
        self._conn.execute(
            "INSERT INTO conversations (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, datetime.now(UTC).isoformat()),
        )
        self._conn.commit()

    def get_recent_messages(self, session_id: str, limit: int = 20) -> list[tuple[str, str]]:
        rows = self._conn.execute(
            """
            SELECT role, content FROM conversations
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
        return [(row["role"], row["content"]) for row in reversed(rows)]

    def count_conversations(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS cnt FROM conversations").fetchone()
        return int(row["cnt"])

    def close(self) -> None:
        self._conn.close()
