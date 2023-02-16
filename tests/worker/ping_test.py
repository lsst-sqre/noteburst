"""Test the ping worker function."""

from __future__ import annotations

from typing import Any

import pytest

from noteburst.worker.functions.ping import ping


@pytest.mark.asyncio
async def test_ping_happy_path(worker_context: dict[Any, Any]) -> None:
    result = await ping(worker_context)
    assert result == "valid identity lock"


@pytest.mark.asyncio
async def test_ping_identity_failure(worker_context: dict[Any, Any]) -> None:
    del worker_context["identity_manager"]
    result = await ping(worker_context)
    assert result == "Failed to query identity"


@pytest.mark.asyncio
async def test_ping_invalid_lock(worker_context: dict[Any, Any]) -> None:
    # Prepare the identity manager state
    identity = await worker_context["identity_manager"].get_identity()
    identity.valid = False

    result = await ping(worker_context)
    assert result == "invalid identity lock"
