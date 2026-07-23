"""Pydantic request/response models — the API contract."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=200)
    website: str = Field("", max_length=500)
    objective: str = Field(..., min_length=1, max_length=1000)


class SessionSummary(BaseModel):
    id: str
    company_name: str
    website: str
    objective: str
    status: str
    created_at: str
    updated_at: str


class SessionDetail(SessionSummary):
    report: Optional[dict[str, Any]] = None
    error: Optional[str] = None


class EventOut(BaseModel):
    seq: int
    node: str
    label: str
    status: str
    payload: Optional[dict[str, Any]] = None
    created_at: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


class ChatMessage(BaseModel):
    role: str
    content: str
    created_at: str


class ChatResponse(BaseModel):
    reply: str
