"""Structured logging setup (BONUS: Logging).

A single ``configure_logging`` call wires up a consistent, timestamped format
across FastAPI, the graph nodes, and the service layer. Every node logs when it
starts and finishes, which makes a failed run easy to trace after the fact.
"""

from __future__ import annotations

import logging
import sys

from .config import get_settings

_CONFIGURED = False


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
    )

    root = logging.getLogger()
    root.setLevel(level)
    # Avoid duplicate handlers if uvicorn's reloader re-imports the module.
    root.handlers = [handler]

    # Uvicorn access logs are noisy in dev; keep them at WARNING.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)
