"""A proof-of-concept worker function."""

from __future__ import annotations

from typing import Any

from structlog.stdlib import get_logger


async def ping(ctx: dict[Any, Any]) -> str:
    """Log a ping message and return a string."""
    logger = None
    try:
        logger = ctx["logger"].bind(task="ping")
        logger.info("Running ping")
        return ctx["identity"].username
    except Exception:
        msg = "Worker context is not set correctly"
        logger = logger or get_logger("worker.functions.ping")
        logger.exception(msg)
        return msg
