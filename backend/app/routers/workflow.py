"""Workflow execution + live progress endpoints."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from ..logging_config import get_logger
from ..schemas import EventOut
from ..services import store
from ..services.runner import run_manager

logger = get_logger("copilot.api.workflow")
router = APIRouter(prefix="/api/sessions", tags=["workflow"])


@router.post("/{session_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_workflow(session_id: str) -> dict:
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    if run_manager.is_running(session_id):
        return {"status": "already_running", "session_id": session_id}
    await run_manager.start(session_id)
    return {"status": "started", "session_id": session_id}


@router.get("/{session_id}/events", response_model=list[EventOut])
def get_events(session_id: str) -> list[EventOut]:
    """Polling fallback: all persisted progress events for a session."""
    if not store.get_session(session_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return [EventOut(**e) for e in store.list_events(session_id)]


@router.get("/{session_id}/stream")
async def stream_events(session_id: str) -> StreamingResponse:
    """Server-Sent Events stream of workflow progress.

    A subscriber first receives a replay of everything persisted so far, then
    live events, so opening the stream at any point shows the full picture.
    """
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")

    # Subscribe BEFORE replaying so no live event slips through the gap. The
    # client de-duplicates by ``seq``.
    queue = run_manager.subscribe(session_id)

    async def event_gen():
        try:
            # 1) Replay persisted history.
            replayed_seq = 0
            for e in store.list_events(session_id):
                replayed_seq = max(replayed_seq, e["seq"])
                yield _sse({"type": "event", **e})

            # 2) If the run is already terminal, close after replay.
            current = store.get_session(session_id)
            if current and current["status"] in ("completed", "failed") and not run_manager.is_running(session_id):
                yield _sse({"type": "done", "status": current["status"], "error": current.get("error")})
                return

            # 3) Stream live events, skipping any already replayed.
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=25.0)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"  # SSE comment to hold the connection
                    continue
                if event.get("type") == "event" and event.get("seq", 0) <= replayed_seq:
                    continue
                yield _sse(event)
                if event.get("type") == "done":
                    return
        finally:
            run_manager.unsubscribe(session_id, queue)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"
