"""Follow-up chat grounded in a session's finished report."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, status

from ..logging_config import get_logger
from ..schemas import ChatMessage, ChatRequest, ChatResponse
from ..services import store
from ..services.llm import get_llm

logger = get_logger("copilot.api.chat")
router = APIRouter(prefix="/api/sessions", tags=["chat"])


def _build_context(report: dict, question: str, history: list[dict]) -> str:
    report_text = json.dumps(report, indent=2)
    history_text = "\n".join(f"{m['role']}: {m['content']}" for m in history[-6:])
    return (
        "Answer the user's question using ONLY the research briefing below. If the "
        "briefing does not contain the answer, say so and point to the 'unknowns' "
        "section rather than guessing.\n"
        f"[[QUESTION]]{question}[[/QUESTION]]\n"
        f"[[COMPANY]]{report.get('company_overview', '')[:120]}[[/COMPANY]]\n"
        f"[[REPORT]]{report_text}[[/REPORT]]\n"
        f"[[HISTORY]]{history_text}[[/HISTORY]]"
    )


@router.post("/{session_id}/chat", response_model=ChatResponse)
def chat(session_id: str, body: ChatRequest) -> ChatResponse:
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    if session["status"] != "completed" or not session.get("report"):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Report is not ready yet — run the workflow to completion first.",
        )

    history = store.list_messages(session_id)
    store.add_message(session_id, "user", body.message)

    llm = get_llm()
    prompt = _build_context(session["report"], body.message, history)
    reply = llm.complete_text(
        system="You are a grounded sales-research assistant. Be concise and honest.",
        prompt=prompt,
    )
    store.add_message(session_id, "assistant", reply)
    return ChatResponse(reply=reply)


@router.get("/{session_id}/messages", response_model=list[ChatMessage])
def get_messages(session_id: str) -> list[ChatMessage]:
    if not store.get_session(session_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return [ChatMessage(**m) for m in store.list_messages(session_id)]
