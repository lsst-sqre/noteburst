"""A proof-of-concept worker function."""

from __future__ import annotations

from typing import Any, Dict


async def ping(ctx: Dict[Any, Any]) -> str:
    try:
        identity = await ctx["identity_manager"].get_identity()
    except Exception:
        return "Failed to query identity"

    if identity.valid is True:
        return "valid identity lock"
    else:
        return "invalid identity lock"
