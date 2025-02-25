"""Tests for handlers of the v1 API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from httpx import AsyncClient
from safir.arq import MockArqQueue
from safir.dependencies.arq import arq_dependency
from safir.metrics import MockEventPublisher

from noteburst.events import events_dependency


@pytest.fixture
def sample_ipynb() -> str:
    path = Path(__file__).parent.joinpath("../data/test.ipynb")
    return path.read_text()


@pytest.fixture
def sample_ipynb_executed() -> str:
    path = Path(__file__).parent.joinpath("../data/test.nbexec.ipynb")
    return path.read_text()


@pytest.mark.asyncio
async def test_post_nbexec(
    client: AsyncClient, sample_ipynb: str, sample_ipynb_executed: str
) -> None:
    """Test ``POST /v1/``, sending a notebook to execute."""
    events = await events_dependency()

    arq_queue = await arq_dependency()
    assert isinstance(arq_queue, MockArqQueue)

    response = await client.post(
        "/noteburst/v1/notebooks/",
        json={
            "ipynb": sample_ipynb,
            "kernel_name": "LSST",
        },
    )
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "queued"
    job_url = data["self_url"]
    assert job_url == response.headers["Location"]
    job_id = data["job_id"]

    pub = cast(MockEventPublisher, events.enqueue_nbexec_success).published
    pub.assert_published_all([{"username": "user"}])

    response = await client.get(job_url)
    assert response.status_code == 200
    data2 = response.json()
    assert data == data2

    assert "source" not in data2
    assert "ipynb" not in data2

    # Request the job with the source ipynb included
    response = await client.get(job_url, params={"source": "true"})
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == sample_ipynb

    # Toggle the job to in-progress; the status should update
    await arq_queue.set_in_progress(job_id)
    response = await client.get(job_url)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "in_progress"

    # Toggle the job to complete
    result = json.dumps(
        {
            "notebook": sample_ipynb_executed,
            "resources": {},
            "error": None,
        }
    )
    await arq_queue.set_complete(job_id, result=result)
    response = await client.get(job_url)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "complete"
    assert data["success"] is True
    assert data["ipynb"] == sample_ipynb_executed

    # Request a job that doesn't exist
    response = await client.get("/noteburst/v1/notebooks/unknown")
    assert response.status_code == 404
    data = response.json()
    print(data)
    assert data["detail"][0]["type"] == "unknown_job"
    assert data["detail"][0]["loc"] == ["path", "job_id"]
    assert data["detail"][0]["msg"] == "Job not found"
