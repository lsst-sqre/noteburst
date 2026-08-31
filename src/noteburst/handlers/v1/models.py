"""JSON message models for the /v1/ API endpoints."""

import asyncio
import json
from datetime import datetime, timedelta
from enum import Enum
from typing import Annotated, Any

from arq.jobs import JobStatus
from fastapi import Request
from pydantic import AnyHttpUrl, BaseModel, Field, field_validator
from rubin.nublado.client import (
    NotebookExecutionError,
    NotebookExecutionResult,
)
from safir.arq import JobMetadata, JobResult
from safir.pydantic import HumanTimedelta

from noteburst.config.frontend import config
from noteburst.exceptions import NbexecTaskError, NbexecTaskTimeoutError

kernel_name_field = Field(
    title="The name of the Jupyter kernel the kernel is executed with",
    examples=["lsst"],
    description=(
        "The default kernel, `lsst`, contains the full Rubin Python "
        "environment, [rubinenv](https://anaconda.org/conda-forge/rubin-env), "
        "which includes the LSST Science Pipelines."
    ),
)


def _format_type_name(value: object) -> str:
    """Format any value's type as a ``module_name.ClassName`` string."""
    value_class = value.__class__
    return f"{value_class.__module__}.{value_class.__name__}"


def _format_exception_type(exception: BaseException) -> str:
    """Format an exception's type as a ``module_name.ClassName`` string."""
    return _format_type_name(exception)


class NotebookError(BaseModel):
    """Information about an exception that occurred during notebook exec."""

    name: Annotated[str, Field(description="The name of the exception.")]
    message: Annotated[str, Field(description="The exception's message.")]

    @classmethod
    def from_nbexec_error(cls, error: NotebookExecutionError) -> NotebookError:
        """Create a NotebookError from NotebookExecutionErrorModel, which
        is the result of execution in ``/user/:username/rubin/execute``.
        """
        return cls(name=error.name, message=error.message)


class NoteburstErrorCodes(Enum):
    """Error codes for Noteburst errors."""

    timeout = "timeout"
    """The notebook execution timed out."""

    jupyter_error = "jupyter_error"
    """An error occurred contacting the Jupyter server."""

    unknown = "unknown"
    """An unknown error occurred."""


class NoteburstExecutionError(BaseModel):
    """Information about an exception that occurred during noteburst's
    execution of a notebook (other than an exception raised in the notebook
    itself).
    """

    code: NoteburstErrorCodes = Field(
        description="The reference code of the error."
    )

    message: str | None = Field(
        None, description="Additional information about the exception."
    )

    exception_type: str | None = Field(
        None,
        description=(
            "The type of the exception. This is a string in the form "
            "`module_name.ClassName`."
        ),
    )


class NotebookResponse(BaseModel):
    """Information about a notebook execution job, possibly including the
    result and source notebooks.
    """

    job_id: Annotated[str, Field(title="The job ID")]

    kernel_name: Annotated[str, kernel_name_field]

    enqueue_time: Annotated[
        datetime, Field(title="Time when the job was added to the queue (UTC)")
    ]

    status: Annotated[
        JobStatus,
        Field(title="The current status of the notebook execution job"),
    ]

    self_url: Annotated[AnyHttpUrl, Field(title="The URL of this resource")]

    source: Annotated[
        str | None,
        Field(
            title="The content of the source ipynb file (JSON-encoded string)",
            description="This field is null unless the source is requested.",
        ),
    ] = None

    start_time: Annotated[
        datetime | None,
        Field(
            title="Time when the notebook execution started (UTC)",
            description="This field is present if the result is available.",
        ),
    ] = None

    finish_time: Annotated[
        datetime | None,
        Field(
            title="Time when the notebook execution completed (UTC)",
            description=(
                "This field is present only if the result is available."
            ),
        ),
    ] = None

    success: Annotated[
        bool | None,
        Field(
            title="Whether the execution was successful or not",
            description="This field is present if the result is available.",
        ),
    ] = None

    error: Annotated[
        NoteburstExecutionError | None,
        Field(
            description=(
                "An error occurred during notebook execution, other than an "
                "exception in the notebook itself. This field is null if an "
                "error did not occur."
            )
        ),
    ] = None

    ipynb: Annotated[
        str | None,
        Field(
            title="The contents of the executed Jupyter notebook",
            description="The ipynb is a JSON-encoded string. This field is "
            "present if the result is available.",
        ),
    ] = None

    ipynb_error: Annotated[
        NotebookError | None,
        Field(
            None,
            title="The error that occurred during notebook execution",
            description="This field is null if an exeception did not occur.",
        ),
    ] = None

    timeout: Annotated[
        float | None,
        Field(
            None,
            title="The job's timeout in seconds",
            description="This field is null if a timeout was not set.",
        ),
    ] = None

    @classmethod
    async def from_job_metadata(
        cls,
        *,
        job: JobMetadata,
        request: Request,
        include_source: bool = False,
        job_result: JobResult | None = None,
    ) -> NotebookResponse:
        """Create a NotebookResponse from a job."""
        # When a job is a "success" it means that the arq worker didn't raise
        # an exception, so we can expect an ipynb result. However the ipynb
        # might have still raised an exception which is part of
        # nbexec_result.error and we want to pass that back to the user.
        if job_result is not None and job_result.success:
            res = NotebookExecutionResult.model_validate_json(
                job_result.result
            )
            ipynb = res.notebook
            if res.error:
                ipynb_error = NotebookError.from_nbexec_error(res.error)
            else:
                ipynb_error = None
        else:
            ipynb = None
            ipynb_error = None

        # In this case the job is complete but failed (an exception was raised)
        # so we want to pass the exception back to the user.
        noteburst_error = None
        if job_result and not job_result.success:
            # Test for None explicitly: a falsy-but-present result (such as an
            # empty string) is still a recorded result and must reach the
            # catch-all below rather than fall through to a null error.
            if (e := job_result.result) is not None:
                if isinstance(e, NbexecTaskTimeoutError):
                    noteburst_error = NoteburstExecutionError(
                        code=NoteburstErrorCodes.timeout,
                        message=str(e).strip(),
                        exception_type=_format_exception_type(e),
                    )
                elif isinstance(e, NbexecTaskError):
                    noteburst_error = NoteburstExecutionError(
                        code=NoteburstErrorCodes.jupyter_error,
                        message=str(e).strip(),
                        exception_type=_format_exception_type(e),
                    )
                elif isinstance(e, TimeoutError):
                    # arq's job_timeout backstop for nbexec cancels the task
                    # and records a bare TimeoutError (asyncio.TimeoutError is
                    # an alias of it since Python 3.11), which usually carries
                    # no message of its own.
                    noteburst_error = NoteburstExecutionError(
                        code=NoteburstErrorCodes.timeout,
                        message=(
                            str(e).strip()
                            or "Notebook execution exceeded its job timeout"
                        ),
                        exception_type=_format_exception_type(e),
                    )
                elif isinstance(e, asyncio.CancelledError):
                    # arq stores a CancelledError as the result of an aborted
                    # job, and also when the worker is shut down mid-job. That
                    # is not a timeout, so report it as unknown but say what
                    # happened.
                    noteburst_error = NoteburstExecutionError(
                        code=NoteburstErrorCodes.unknown,
                        message=(
                            str(e).strip()
                            or "Notebook execution was cancelled before it "
                            "finished; the job was aborted or its worker "
                            "shut down"
                        ),
                        exception_type=_format_exception_type(e),
                    )
                else:
                    # Catch-all for any other result, including BaseException
                    # subclasses that are not Exceptions, so that a failed job
                    # never reports a null error.
                    noteburst_error = NoteburstExecutionError(
                        code=NoteburstErrorCodes.unknown,
                        # Fall back to the type name so that clients never
                        # receive an error without any diagnostic content.
                        message=str(e).strip() or _format_type_name(e),
                        # arq's stored result is untyped, so only report an
                        # exception type when the result really is one.
                        exception_type=(
                            _format_exception_type(e)
                            if isinstance(e, BaseException)
                            else None
                        ),
                    )
            else:
                # arq recorded a failure but no result to explain it. Report a
                # populated error anyway; do not invent an exception type,
                # since there is no exception here to name.
                noteburst_error = NoteburstExecutionError(
                    code=NoteburstErrorCodes.unknown,
                    message=(
                        "The notebook execution job failed without recording "
                        "an exception."
                    ),
                )

        return cls(
            job_id=job.id,
            enqueue_time=job.enqueue_time,
            status=job.status,
            kernel_name=job.kwargs["kernel_name"],
            source=job.kwargs["ipynb"] if include_source else None,
            self_url=AnyHttpUrl(
                str(request.url_for("get_nbexec_job", job_id=job.id))
            ),
            start_time=job_result.start_time if job_result else None,
            finish_time=job_result.finish_time if job_result else None,
            success=job_result.success if job_result else None,
            error=noteburst_error,
            ipynb=ipynb,
            ipynb_error=ipynb_error,
            timeout=job.kwargs["timeout"].total_seconds(),
        )


class PostNotebookRequest(BaseModel):
    """The ``POST /notebooks/`` request body."""

    ipynb: Annotated[
        str | dict[str, Any],
        Field(
            title="The contents of a Jupyter notebook",
            description="If a string, the content is parsed as JSON. "
            "Alternatively, the content can be submitted pre-parsed as "
            "an object.",
        ),
    ]

    kernel_name: Annotated[str, kernel_name_field] = "lsst"

    timeout: HumanTimedelta = Field(
        default_factory=lambda: timedelta(seconds=300),
        title="Timeout for notebook execution.",
        description=(
            "The timeout can either be written as a number in seconds or as a "
            "human-readable duration string. For example, '5m' is 5 minutes, "
            "'1h' is 1 hour, '1d' is 1 day. If the notebook execution does "
            "not complete within this time, the job is marked as failed with "
            "a `timeout` error code.\n\n"
            "This timeout is what ends an over-running notebook. The worker "
            "also registers an absolute arq timeout for notebook execution, "
            "`NOTEBURST_WORKER_NBEXEC_JOB_TIMEOUT`, as a backstop. Requests "
            "whose timeout is not comfortably under that backstop are "
            "rejected with a 422 error, so the backstop can fire only if "
            "this timeout somehow does not. With the default configuration "
            "the longest accepted timeout is one hour."
        ),
    )

    @field_validator("timeout")
    @classmethod
    def _check_timeout_under_nbexec_backstop(
        cls, value: timedelta
    ) -> timedelta:
        """Reject timeouts that arq's nbexec backstop would cancel first.

        If a request timeout could outlive the worker's absolute nbexec
        timeout, arq would cancel the job and the response would misreport
        the run as exhausting the requested timeout.
        """
        limit = config.max_notebook_timeout
        if value > limit:
            raise ValueError(
                f"timeout must be {limit.total_seconds():.0f} seconds or "
                "less, so that it fires before the worker's absolute "
                "notebook execution timeout "
                f"(NOTEBURST_WORKER_NBEXEC_JOB_TIMEOUT, currently "
                f"{config.nbexec_job_timeout} seconds)"
            )
        return value

    enable_retry: Annotated[
        bool,
        Field(
            title="Enable retries on failures",
            description=(
                "If true (default), noteburst will retry notebook "
                "execution if the notebook fails, with an increasing back-off "
                "time between tries. This is useful for dealing with "
                "transient issues. However, if you are using Noteburst for "
                "continuous integration of notebooks, disabling retries "
                "provides faster feedback."
            ),
        ),
    ] = True

    def get_ipynb_as_str(self) -> str:
        """Get the ipynb as a JSON-encoded string."""
        if isinstance(self.ipynb, str):
            return self.ipynb
        else:
            return json.dumps(self.ipynb)
