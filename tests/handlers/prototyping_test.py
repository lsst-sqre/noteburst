"""Tests for the prototyping endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from noteburst.dependencies.arqpool import MockArqQueue, arq_dependency

if TYPE_CHECKING:
    from httpx import AsyncClient


@pytest.mark.asyncio
async def test_post_ping(client: AsyncClient) -> None:
    """Test ``POST /prototype/ping``."""
    arq_queue = await arq_dependency()
    assert isinstance(arq_queue, MockArqQueue)

    response = await client.post("/noteburst/prototype/ping")
    assert response.status_code == 202
    data = response.json()
    assert data["task_name"] == "ping"
    assert data["status"] == "queued"
    job_url = data["self_url"]
    job_id = data["job_id"]

    response = await client.get(job_url)
    assert response.status_code == 200
    data2 = response.json()
    assert data == data2

    # Toggle the job to in-progress; the status should update
    await arq_queue.set_in_progress(job_id)
    response = await client.get(job_url)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "in_progress"

    # Toggle the job to complete
    await arq_queue.set_complete(job_id, result="pong")
    response = await client.get(job_url)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "complete"
    result_url = data["result_url"]

    response = await client.get(result_url)
    assert response.status_code == 200
    data = response.json()
    assert data["result"] == "pong"
