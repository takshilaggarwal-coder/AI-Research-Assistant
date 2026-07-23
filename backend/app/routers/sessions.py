"""Session CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ..logging_config import get_logger
from ..schemas import SessionCreate, SessionDetail, SessionSummary
from ..services import store

logger = get_logger("copilot.api.sessions")
router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=SessionDetail, status_code=status.HTTP_201_CREATED)
def create_session(body: SessionCreate) -> SessionDetail:
    session = store.create_session(body.company_name, body.website, body.objective)
    logger.info("Created session %s for %s", session["id"], body.company_name)
    return SessionDetail(**session)


@router.get("", response_model=list[SessionSummary])
def list_sessions() -> list[SessionSummary]:
    return [SessionSummary(**s) for s in store.list_sessions()]


@router.get("/{session_id}", response_model=SessionDetail)
def get_session(session_id: str) -> SessionDetail:
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return SessionDetail(**session)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str) -> None:
    if not store.get_session(session_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    store.delete_session(session_id)
