"""Tests for the v1 API response models."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from arq.jobs import JobStatus
from fastapi import Request
from pydantic import ValidationError
from safir.arq import JobMetadata, JobResult

from noteburst.exceptions import NbexecTaskError, NbexecTaskTimeoutError
from noteburst.handlers.v1.models import (
    NotebookResponse,
    NoteburstErrorCodes,
    PostNotebookRequest,
)
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


class CustomBaseError(BaseException):
    """A `BaseException` subclass that is not an `Exception`.

    This stands in for any non-`Exception` result that arq might store for a
    failed job, and guards the fallback branch of the failed-job chain.
    """


def build_failed_job(
    result: object,
) -> tuple[JobMetadata, JobResult]:
    """Build the metadata and result of an nbexec job that failed, storing the
    given object as the job's result.

    The result is usually the exception that the job raised, but arq's stored
    result is untyped, so this accepts any object (including `None`) to
    exercise the classifier's fallbacks.
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
        result=result,
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
    assert "worker job timeout" not in response.error.message
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
    assert (
        response.error.exception_type
        == "noteburst.exceptions.NbexecTaskTimeoutError"
    )


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
    assert (
        response.error.exception_type == "noteburst.exceptions.NbexecTaskError"
    )


@pytest.mark.asyncio
async def test_cancelled_error() -> None:
    """Test that an aborted job, for which arq stores an
    `asyncio.CancelledError`, is reported with a populated error that does not
    claim the job timed out.
    """
    job, job_result = build_failed_job(asyncio.CancelledError())
    response = await NotebookResponse.from_job_metadata(
        job=job, request=build_request(), job_result=job_result
    )
    assert response.error is not None
    assert response.error.code != NoteburstErrorCodes.timeout
    assert response.error.code == NoteburstErrorCodes.unknown
    assert response.error.message
    assert "cancelled" in response.error.message.lower()
    assert response.error.exception_type == "asyncio.exceptions.CancelledError"


@pytest.mark.asyncio
async def test_base_exception_is_reported() -> None:
    """Test that a failed job whose result is a `BaseException` that is not an
    `Exception` still yields a populated error, rather than ``error: null``.
    """
    job, job_result = build_failed_job(CustomBaseError())
    response = await NotebookResponse.from_job_metadata(
        job=job, request=build_request(), job_result=job_result
    )
    assert response.success is False
    assert response.error is not None
    assert response.error.code == NoteburstErrorCodes.unknown
    assert response.error.message
    assert response.error.exception_type == (
        "tests.handlers.v1_models_test.CustomBaseError"
    )


@pytest.mark.asyncio
async def test_base_exception_with_message() -> None:
    """Test that a non-`Exception` `BaseException` keeps its own message."""
    job, job_result = build_failed_job(CustomBaseError("Worker shut down"))
    response = await NotebookResponse.from_job_metadata(
        job=job, request=build_request(), job_result=job_result
    )
    assert response.error is not None
    assert response.error.message == "Worker shut down"


@pytest.mark.asyncio
async def test_missing_result() -> None:
    """Test that a failed job that recorded no result at all still yields a
    populated error, rather than ``error: null``.
    """
    job, job_result = build_failed_job(None)
    response = await NotebookResponse.from_job_metadata(
        job=job, request=build_request(), job_result=job_result
    )
    assert response.success is False
    assert response.error is not None
    assert response.error.code == NoteburstErrorCodes.unknown
    assert response.error.message
    assert "without recording an exception" in response.error.message
    # A missing result has no exception, so no type should be synthesized;
    # in particular the response must not claim the job raised a NoneType.
    assert response.error.exception_type is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "result",
    [
        pytest.param("", id="empty-string"),
        pytest.param(0, id="zero"),
        pytest.param(False, id="false"),
    ],
)
async def test_falsy_result(result: object) -> None:
    """Test that a failed job whose result is present but falsy reaches the
    catch-all branch and yields a populated error.
    """
    job, job_result = build_failed_job(result)
    response = await NotebookResponse.from_job_metadata(
        job=job, request=build_request(), job_result=job_result
    )
    assert response.success is False
    assert response.error is not None
    assert response.error.code == NoteburstErrorCodes.unknown
    assert response.error.message
    # None of these results are exceptions, so no exception type is reported.
    assert response.error.exception_type is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "result",
    [
        pytest.param(None, id="none"),
        pytest.param("", id="empty-string"),
        pytest.param(0, id="zero"),
        pytest.param(False, id="false"),
        pytest.param(asyncio.CancelledError(), id="cancelled"),
        pytest.param(CustomBaseError(), id="base-exception"),
        pytest.param(TimeoutError(), id="bare-timeout"),
        pytest.param(RuntimeError(), id="runtime-error"),
        pytest.param(
            NbexecTaskError.from_exception(RuntimeError("Jupyter is down")),
            id="nbexec-task-error",
        ),
        pytest.param(
            NbexecTaskTimeoutError.from_exception(TimeoutError()),
            id="nbexec-timeout-error",
        ),
    ],
)
async def test_failed_job_always_reports_an_error(result: object) -> None:
    """Test that no ``success: false`` response can carry ``error: null``,
    whatever arq stored as the job's result.
    """
    job, job_result = build_failed_job(result)
    response = await NotebookResponse.from_job_metadata(
        job=job, request=build_request(), job_result=job_result
    )
    assert response.success is False
    assert response.error is not None
    assert response.error.message


def test_timeout_rejected_above_nbexec_backstop() -> None:
    """Test that a request timeout that arq's nbexec backstop could cancel
    first is rejected, rather than accepted and later misreported.
    """
    with pytest.raises(ValidationError) as excinfo:
        PostNotebookRequest(ipynb="{}", timeout=timedelta(hours=2))
    message = str(excinfo.value)
    assert "NOTEBURST_WORKER_NBEXEC_JOB_TIMEOUT" in message
    # The default backstop is 3660s with a 60s margin, so the limit named in
    # the error is 3600 seconds.
    assert "3600" in message


def test_timeout_accepted_at_maximum() -> None:
    """Test that the longest permitted timeout (the backstop minus the
    60-second margin; one hour at the default configuration) is accepted.
    """
    request = PostNotebookRequest(ipynb="{}", timeout=timedelta(hours=1))
    assert request.timeout == timedelta(hours=1)


def test_timeout_field_description() -> None:
    """Test that the public description of ``PostNotebookRequest.timeout``
    describes the timeout mechanism the service actually implements.

    This text is emitted into the OpenAPI schema, so clients such as Times
    Square read it as the contract for what bounds notebook execution.
    """
    description = PostNotebookRequest.model_fields["timeout"].description
    assert description is not None

    # The grace margin (NOTEBURST_JOB_TIMEOUT_GRACE) no longer exists; nbexec
    # has a dedicated arq timeout instead.
    assert "grace" not in description

    # The worker-wide job timeout does not bound notebook execution at all,
    # so it must not be described as the backstop or as a ceiling on what a
    # request may ask for.
    assert "worker-wide" not in description
    assert "NOTEBURST_WORKER_JOB_TIMEOUT" not in description

    # The arq backstop for notebook execution is the nbexec-specific timeout,
    # and the contract that the request timeout stays under it is enforced by
    # rejecting over-long requests.
    assert "NOTEBURST_WORKER_NBEXEC_JOB_TIMEOUT" in description
    assert "rejected" in description
