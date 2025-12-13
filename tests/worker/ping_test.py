"""Test the ping worker function."""

from __future__ import annotations

from typing import Any

import pytest

from noteburst.worker.functions.ping import ping


@pytest.mark.asyncio
async def test_ping_happy_path(worker_context: dict[Any, Any]) -> None:
    result = await ping(worker_context)
    assert result == "bot-test"


@pytest.mark.asyncio
async def test_ping_bad_context(worker_context: dict[Any, Any]) -> None:
    del worker_context["identity"]
    result = await ping(worker_context)
    assert result == "Worker context is not set correctly"
