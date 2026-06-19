import json
from datetime import UTC, datetime
from pathlib import Path

from smith.memory.db import get_connection
from smith.tools.project_context import AnalysisProjectContext


class ProjectContextStore:
    def __init__(self, db_path: Path | str) -> None:
        self._conn = get_connection(db_path)

    def save(self, context: AnalysisProjectContext) -> None:
        self._conn.execute(
            """
            INSERT INTO project_contexts (project_path, generated_at, context_json)
            VALUES (?, ?, ?)
            """,
            (
                context.project_path,
                datetime.now(UTC).isoformat(),
                json.dumps(context.to_dict()),
            ),
        )
        self._conn.commit()

    def get_latest(self, project_path: str | Path) -> AnalysisProjectContext | None:
        resolved = str(Path(project_path).expanduser().resolve())
        row = self._conn.execute(
            """
            SELECT context_json FROM project_contexts
            WHERE project_path = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (resolved,),
        ).fetchone()
        if not row:
            return None
        return AnalysisProjectContext.from_dict(json.loads(row["context_json"]))

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS cnt FROM project_contexts").fetchone()
        return int(row["cnt"])

    def close(self) -> None:
        self._conn.close()
