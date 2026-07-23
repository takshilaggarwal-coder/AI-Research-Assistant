"""SQLite persistence layer.

A plain ``sqlite3`` layer (no ORM) keeps the dependency surface small and the
schema obvious. WAL mode plus a fresh connection per operation gives us safe
concurrent reads/writes across FastAPI's threadpool without a global lock.

Tables
------
* ``sessions``  — one row per research session (inputs, status, report JSON).
* ``events``    — append-only workflow progress log (one row per node step).
* ``messages``  — follow-up chat history per session.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from .config import get_settings
from .logging_config import get_logger

logger = get_logger("copilot.db")


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    settings = get_settings()
    conn = sqlite3.connect(settings.database_path, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id            TEXT PRIMARY KEY,
    company_name  TEXT NOT NULL,
    website       TEXT,
    objective     TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'created',  -- created|running|completed|failed
    report_json   TEXT,
    error         TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    seq         INTEGER NOT NULL,
    node        TEXT NOT NULL,
    label       TEXT NOT NULL,
    status      TEXT NOT NULL,          -- running|completed|failed
    payload_json TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role        TEXT NOT NULL,          -- user|assistant
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id, seq);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);
"""


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)
    logger.info("Database initialized")
