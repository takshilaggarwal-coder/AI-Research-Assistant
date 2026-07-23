"""Background workflow runner + live progress fan-out.

The graph itself is synchronous (LangGraph's ``.stream`` is a generator). To
keep FastAPI's event loop responsive we run that generator in a worker thread
and bridge each emitted step back onto the loop via ``call_soon_threadsafe``,
where it is (a) persisted to the ``events`` table and (b) fanned out to any
connected SSE subscribers.

This gives us three properties at once:
    * live progress in the UI (SSE),
    * a durable audit trail (events table), and
    * a late subscriber can replay history and still catch live events.
"""

from __future__ import annotations

import asyncio
from typing import Any

from ..logging_config import get_logger
from ..graph import workflow
from . import store

logger = get_logger("copilot.runner")


def _summarize(node: str, update: dict[str, Any]) -> dict[str, Any]:
    """Compact, UI-friendly view of a node's output for the progress feed."""
    payload: dict[str, Any] = {}
    if "plan" in update:
        payload["plan"] = update["plan"]
        payload["search_queries"] = update.get("search_queries", [])
    if "findings" in update:
        payload["findings_count"] = len(update["findings"])
        payload["sources_count"] = len(update.get("sources", []))
    if "analysis" in update:
        payload["confidence"] = update["analysis"].get("confidence")
    if "quality_score" in update:
        payload["quality_score"] = update["quality_score"]
        payload["quality_issues"] = update.get("quality_issues", [])
        payload["quality_passed"] = update.get("quality_passed")
    if update.get("errors"):
        payload["errors"] = update["errors"]
    if update.get("logs"):
        payload["logs"] = update["logs"]
    return payload


class RunManager:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._running: set[str] = set()

    # ---------------- subscription (SSE) ---------------- #
    def subscribe(self, session_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(session_id, []).append(q)
        return q

    def unsubscribe(self, session_id: str, q: asyncio.Queue) -> None:
        subs = self._subscribers.get(session_id, [])
        if q in subs:
            subs.remove(q)

    def _publish(self, session_id: str, event: dict) -> None:
        for q in self._subscribers.get(session_id, []):
            q.put_nowait(event)

    def is_running(self, session_id: str) -> bool:
        return session_id in self._running

    # ---------------- run lifecycle ---------------- #
    async def start(self, session_id: str) -> None:
        if session_id in self._running:
            logger.info("Run already in progress for %s", session_id)
            return
        session = store.get_session(session_id)
        if not session:
            raise ValueError("session not found")

        self._running.add(session_id)
        store.update_session_status(session_id, "running")
        self._publish(session_id, {"type": "status", "status": "running"})
        # Fire-and-forget; the SSE stream reports completion.
        asyncio.create_task(self._run(session_id, session))

    async def _run(self, session_id: str, session: dict) -> None:
        loop = asyncio.get_running_loop()
        try:
            await asyncio.to_thread(self._run_blocking, session_id, session, loop)
        finally:
            self._running.discard(session_id)

    def _run_blocking(self, session_id: str, session: dict, loop) -> None:
        state = {
            "session_id": session_id,
            "company_name": session["company_name"],
            "website": session["website"],
            "objective": session["objective"],
            "retries": 0,
        }
        seq = 0
        try:
            for event in workflow.stream_run(state, thread_id=session_id):
                seq += 1
                node, label, update = event["node"], event["label"], event["update"]
                status = "failed" if update.get("errors") else "completed"
                payload = _summarize(node, update)
                store.add_event(session_id, seq, node, label, status, payload)
                loop.call_soon_threadsafe(
                    self._publish,
                    session_id,
                    {
                        "type": "event",
                        "seq": seq,
                        "node": node,
                        "label": label,
                        "status": status,
                        "payload": payload,
                    },
                )

            final = workflow.get_state_snapshot(session_id)
            report = final.get("report")
            store.update_session_status(session_id, "completed", report=report)
            loop.call_soon_threadsafe(
                self._publish, session_id, {"type": "done", "status": "completed"}
            )
            logger.info("Run completed for %s (%d steps)", session_id, seq)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Run failed for %s", session_id)
            store.update_session_status(session_id, "failed", error=str(exc))
            loop.call_soon_threadsafe(
                self._publish,
                session_id,
                {"type": "done", "status": "failed", "error": str(exc)},
            )


# Process-wide singleton.
run_manager = RunManager()
