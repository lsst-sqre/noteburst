"""A proof-of-concept worker function."""

from __future__ import annotations

from typing import Any


async def ping(ctx: dict[Any, Any]) -> str:
    logger = ctx["logger"].bind(task="ping")
    logger.info("Running ping")

    try:
        identity = await ctx["identity_manager"].get_identity()
    except Exception:
        return "Failed to query identity"

    if identity.valid is True:
        return "valid identity lock"
    else:
        return "invalid identity lock"
