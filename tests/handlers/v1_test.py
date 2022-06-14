"""Tests for handlers of the v1 API."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from safir.arq import MockArqQueue
from safir.dependencies.arq import arq_dependency

if TYPE_CHECKING:
    from httpx import AsyncClient


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

    response = await client.get(job_url)
    assert response.status_code == 200
    data2 = response.json()
    assert data == data2

    assert "source" not in data2.keys()
    assert "ipynb" not in data2.keys()

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
    await arq_queue.set_complete(job_id, result=sample_ipynb_executed)
    response = await client.get(job_url)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "complete"
    assert data["success"] is True
    assert data["ipynb"] == sample_ipynb_executed
