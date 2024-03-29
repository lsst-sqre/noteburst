"""JSON message models for the /v1/ API endpoints."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated, Any

from arq.jobs import JobStatus
from fastapi import Request
from pydantic import AnyHttpUrl, BaseModel, Field
from safir.arq import JobMetadata, JobResult

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
        if job_result is not None and job_result.success:
            nbexec_result = NotebookExecutionResult.model_validate_json(
                job_result.result
            )
            ipynb = nbexec_result.notebook
            if nbexec_result.error:
                error = NotebookError.from_nbexec_error(nbexec_result.error)
            else:
                error = None
        else:
            ipynb = None
            error = None

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
            ipynb=ipynb,
            ipynb_error=error,
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
