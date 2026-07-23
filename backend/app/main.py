"""FastAPI application entrypoint.

Run with:  uvicorn app.main:app --reload  (from the ``backend/`` directory)
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.requests import Request

from .config import get_settings
from .database import init_db
from .logging_config import configure_logging, get_logger
from .routers import chat, sessions, workflow

logger = get_logger("copilot.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    init_db()
    logger.info(
        "Starting %s | env=%s | llm=%s | search=%s",
        settings.app_name,
        settings.environment,
        settings.llm_mode,
        settings.search_mode,
    )
    yield
    logger.info("Shutting down")


settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Last-resort handler so the client always gets structured JSON."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    return {
        "status": "ok",
        "llm_mode": settings.llm_mode,
        "search_mode": settings.search_mode,
    }


app.include_router(sessions.router)
app.include_router(workflow.router)
app.include_router(chat.router)
