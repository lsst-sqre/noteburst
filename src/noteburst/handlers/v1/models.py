"""JSON message models for the /v1/ API endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from enum import Enum
from typing import Annotated, Any

from arq.jobs import JobStatus
from fastapi import Request
from pydantic import AnyHttpUrl, BaseModel, Field
from safir.arq import JobMetadata, JobResult
from safir.pydantic import HumanTimedelta

from noteburst.exceptions import NbexecTaskError, NbexecTaskTimeoutError
from noteburst.jupyterclient.jupyterlab import (
    NotebookExecutionErrorModel,
    NotebookExecutionResult,
)

kernel_name_field = Field(
    "LSST",
    title="The name of the Jupyter kernel the kernel is executed with",
    examples=["LSST"],
    description=(
        "The default kernel, LSST, contains the full Rubin Python "
        "environment, [rubinenv](https://anaconda.org/conda-forge/rubin-env), "
        "which includes the LSST Science Pipelines."
    ),
)


class NotebookError(BaseModel):
    """Information about an exception that occurred during notebook exec."""

    name: Annotated[str, Field(description="The name of the exception.")]
    message: Annotated[str, Field(description="The exception's message.")]

    @classmethod
    def from_nbexec_error(
        cls, error: NotebookExecutionErrorModel
    ) -> NotebookError:
        """Create a NotebookError from a NotebookExecutionErrorModel, which
        is the result of execution in ``/user/:username/rubin/execute``.
        """
        return cls(
            name=error.ename,
            message=error.err_msg,
        )


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
            nbexec_result = NotebookExecutionResult.model_validate_json(
                job_result.result
            )
            ipynb = nbexec_result.notebook
            if nbexec_result.error:
                ipynb_error = NotebookError.from_nbexec_error(
                    nbexec_result.error
                )
            else:
                ipynb_error = None
        else:
            ipynb = None
            ipynb_error = None

        # In this case the job is complete but failed (an exception was raised)
        # so we want to pass the exception back to the user.
        noteburst_error = None
        if job_result and not job_result.success:
            if e := job_result.result:
                if isinstance(job_result.result, NbexecTaskTimeoutError):
                    noteburst_error = NoteburstExecutionError(
                        code=NoteburstErrorCodes.timeout,
                        message=str(e).strip(),
                    )
                elif isinstance(job_result.result, NbexecTaskError):
                    noteburst_error = NoteburstExecutionError(
                        code=NoteburstErrorCodes.jupyter_error,
                        message=str(e).strip(),
                    )
                elif isinstance(job_result.result, Exception):
                    noteburst_error = NoteburstExecutionError(
                        code=NoteburstErrorCodes.unknown,
                        message=str(e).strip(),
                    )

        return cls(
            job_id=job.id,
            enqueue_time=job.enqueue_time,
            status=job.status,
            kernel_name=job.kwargs["kernel_name"],
            source=job.kwargs["ipynb"] if include_source else None,
            self_url=str(request.url_for("get_nbexec_job", job_id=job.id)),
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

    kernel_name: Annotated[str, kernel_name_field]

    timeout: HumanTimedelta = Field(
        default_factory=lambda: timedelta(seconds=300),
        title="Timeout for notebook execution.",
        description=(
            "The timeout can either be written as a number in seconds or as a "
            "human-readable duration string. For example, '5m' is 5 minutes, "
            "'1h' is 1 hour, '1d' is 1 day. If the notebook execution does "
            "not complete within this time, the job is marked as failed."
        ),
    )

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
