import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS project_contexts (
    id INTEGER PRIMARY KEY,
    project_path TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    context_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_project_contexts_path ON project_contexts(project_path);
"""


def get_connection(db_path: Path | str) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn
