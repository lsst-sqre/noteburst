"""Tests for the prototyping endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient


@pytest.mark.asyncio
async def test_post_ping(client: AsyncClient) -> None:
    """Test ``POST /prototype/ping``."""
    response = await client.post("/noteburst/prototype/ping")
    assert response.status_code == 202
    data = response.json()
    assert data["task_name"] == "ping"
    job_url = data["self_url"]

    response = await client.get(job_url)
    assert response.status_code == 200
    data2 = response.json()
    assert data == data2
