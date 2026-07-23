"""Repository functions — the only module that touches SQL directly.

Keeping all queries here means the routers stay thin and the storage engine
could be swapped (Postgres, etc.) without touching request handlers.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from ..database import get_conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_session(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "company_name": row["company_name"],
        "website": row["website"] or "",
        "objective": row["objective"],
        "status": row["status"],
        "report": json.loads(row["report_json"]) if row["report_json"] else None,
        "error": row["error"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# --------------------------- sessions --------------------------- #
def create_session(company_name: str, website: str, objective: str) -> dict[str, Any]:
    session_id = uuid.uuid4().hex
    now = _now()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sessions (id, company_name, website, objective, status, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, 'created', ?, ?)",
            (session_id, company_name, website, objective, now, now),
        )
    return get_session(session_id)  # type: ignore[return-value]


def get_session(session_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return _row_to_session(row) if row else None


def list_sessions() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM sessions ORDER BY created_at DESC").fetchall()
    return [_row_to_session(r) for r in rows]


def update_session_status(
    session_id: str,
    status: str,
    report: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET status = ?, report_json = COALESCE(?, report_json), "
            "error = ?, updated_at = ? WHERE id = ?",
            (
                status,
                json.dumps(report) if report is not None else None,
                error,
                _now(),
                session_id,
            ),
        )


def delete_session(session_id: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


# --------------------------- events --------------------------- #
def add_event(
    session_id: str, seq: int, node: str, label: str, status: str, payload: dict | None
) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO events (session_id, seq, node, label, status, payload_json, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                seq,
                node,
                label,
                status,
                json.dumps(payload) if payload is not None else None,
                _now(),
            ),
        )


def list_events(session_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM events WHERE session_id = ? ORDER BY seq ASC", (session_id,)
        ).fetchall()
    return [
        {
            "seq": r["seq"],
            "node": r["node"],
            "label": r["label"],
            "status": r["status"],
            "payload": json.loads(r["payload_json"]) if r["payload_json"] else None,
            "created_at": r["created_at"],
        }
        for r in rows
    ]


# --------------------------- messages --------------------------- #
def add_message(session_id: str, role: str, content: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) "
            "VALUES (?, ?, ?, ?)",
            (session_id, role, content, _now()),
        )


def list_messages(session_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,)
        ).fetchall()
    return [
        {"role": r["role"], "content": r["content"], "created_at": r["created_at"]}
        for r in rows
    ]
