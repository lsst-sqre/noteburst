"""Tests for the v1 API response models."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from arq.jobs import JobStatus
from fastapi import Request
from safir.arq import JobMetadata, JobResult

from noteburst.exceptions import NbexecTaskError, NbexecTaskTimeoutError
from noteburst.handlers.v1.models import NotebookResponse, NoteburstErrorCodes
from noteburst.main import app


def build_request() -> Request:
    """Build a minimal request, which the response models use to construct
    the ``self_url`` of a job.
    """
    scope: dict[str, Any] = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": "/noteburst/v1/notebooks/job-id",
        "raw_path": b"/noteburst/v1/notebooks/job-id",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"example.com")],
        "server": ("example.com", 443),
        "client": ("127.0.0.1", 1234),
        "app": app,
        "router": app.router,
    }
    return Request(scope)


def build_failed_job(exception: Exception) -> tuple[JobMetadata, JobResult]:
    """Build the metadata and result of an nbexec job that failed with the
    given exception.
    """
    timestamp = datetime.now(tz=UTC)
    job = JobMetadata(
        id="job-id",
        name="nbexec",
        args=(),
        kwargs={
            "ipynb": "{}",
            "kernel_name": "lsst",
            "enable_retry": True,
            "timeout": timedelta(seconds=300),
        },
        enqueue_time=timestamp,
        status=JobStatus.complete,
        queue_name="arq:queue",
    )
    job_result = JobResult(
        id=job.id,
        name=job.name,
        args=job.args,
        kwargs=job.kwargs,
        enqueue_time=job.enqueue_time,
        status=job.status,
        queue_name=job.queue_name,
        start_time=timestamp,
        finish_time=timestamp,
        success=False,
        result=exception,
    )
    return job, job_result


@pytest.mark.asyncio
async def test_bare_timeout_error() -> None:
    """Test that a bare `TimeoutError` (raised by arq's own ``job_timeout``
    backstop, rather than by nbexec itself) is reported as a timeout.

    Since Python 3.11 `asyncio.TimeoutError` is an alias of the built-in
    `TimeoutError`, so this covers both.
    """
    job, job_result = build_failed_job(TimeoutError())
    response = await NotebookResponse.from_job_metadata(
        job=job, request=build_request(), job_result=job_result
    )
    assert response.error is not None
    assert response.error.code == NoteburstErrorCodes.timeout
    assert response.error.message
    assert response.error.exception_type == "builtins.TimeoutError"


@pytest.mark.asyncio
async def test_bare_timeout_error_with_message() -> None:
    """Test that a bare `TimeoutError` that does carry a message keeps that
    message.
    """
    job, job_result = build_failed_job(TimeoutError("Timed out after 300s"))
    response = await NotebookResponse.from_job_metadata(
        job=job, request=build_request(), job_result=job_result
    )
    assert response.error is not None
    assert response.error.code == NoteburstErrorCodes.timeout
    assert response.error.message == "Timed out after 300s"


@pytest.mark.asyncio
async def test_unknown_error_with_empty_message() -> None:
    """Test that an unrecognized exception without a message is reported
    with its type name as the message, rather than an empty message.
    """
    job, job_result = build_failed_job(RuntimeError())
    response = await NotebookResponse.from_job_metadata(
        job=job, request=build_request(), job_result=job_result
    )
    assert response.error is not None
    assert response.error.code == NoteburstErrorCodes.unknown
    assert response.error.message == "builtins.RuntimeError"
    assert response.error.exception_type == "builtins.RuntimeError"


@pytest.mark.asyncio
async def test_unknown_error_with_message() -> None:
    """Test that an unrecognized exception's own message is preserved."""
    job, job_result = build_failed_job(RuntimeError("Something went wrong"))
    response = await NotebookResponse.from_job_metadata(
        job=job, request=build_request(), job_result=job_result
    )
    assert response.error is not None
    assert response.error.code == NoteburstErrorCodes.unknown
    assert response.error.message == "Something went wrong"
    assert response.error.exception_type == "builtins.RuntimeError"


@pytest.mark.asyncio
async def test_nbexec_timeout_error() -> None:
    """Test that nbexec's own timeout error is reported as a timeout."""
    job, job_result = build_failed_job(
        NbexecTaskTimeoutError.from_exception(TimeoutError())
    )
    response = await NotebookResponse.from_job_metadata(
        job=job, request=build_request(), job_result=job_result
    )
    assert response.error is not None
    assert response.error.code == NoteburstErrorCodes.timeout
    assert response.error.message
    assert response.error.message.startswith("nbexec timeout error")


@pytest.mark.asyncio
async def test_nbexec_task_error() -> None:
    """Test that a general nbexec task error is reported as a Jupyter error."""
    job, job_result = build_failed_job(
        NbexecTaskError.from_exception(RuntimeError("Jupyter is down"))
    )
    response = await NotebookResponse.from_job_metadata(
        job=job, request=build_request(), job_result=job_result
    )
    assert response.error is not None
    assert response.error.code == NoteburstErrorCodes.jupyter_error
    assert response.error.message
    assert "Jupyter is down" in response.error.message
