"""Test the ``keep_alive`` worker function."""

from __future__ import annotations

from typing import Any

import pytest

from noteburst.worker.functions.keepalive import keep_alive


@pytest.mark.asyncio
async def test_keep_alive_happy_path(worker_context: dict[Any, Any]) -> None:
    result = await keep_alive(worker_context)
    assert result == "alive\n"
