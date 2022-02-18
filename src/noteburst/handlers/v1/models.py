"""JSON message models for the /v1/ API endpoints."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional, Union

from arq.jobs import JobStatus
from fastapi import Request
from pydantic import AnyHttpUrl, BaseModel

from noteburst.dependencies.arqpool import JobMetadata, JobResult


class NotebookResponse(BaseModel):
    """Information about a notebook execution job, possibly including the
    result and source notebooks.
    """

    job_id: str
    """The job ID."""

    kernel_name: str
    """Name of the kernel the notebook is executed with."""

    enqueue_time: datetime
    """Time when the job was added to the queue (UTC)."""

    status: JobStatus
    """The current status of the notebook execution job."""

    self_url: AnyHttpUrl
    """The URL of this resource."""

    source: Optional[str] = None
    """The content of the source ipynb file (JSON-encoded string)."""

    start_time: Optional[datetime] = None
    """Time when the job started (UTC).

    This field is present if the result is available.
    """

    finish_time: Optional[datetime] = None
    """Time when the job completed (UTC).

    This field is present if the result is available.
    """

    success: Optional[bool] = None
    """Whether the execution was successful or not.

    This field is present if the result is available.
    """

    ipynb: Optional[str] = None
    """The contents of the executed Jupyter notebook.

    This field is present if the result is available.
    """

    @classmethod
    async def from_job_metadata(
        cls,
        *,
        job: JobMetadata,
        request: Request,
        include_source: bool = False,
        job_result: Optional[JobResult] = None,
    ) -> NotebookResponse:
        return cls(
            job_id=job.id,
            enqueue_time=job.enqueue_time,
            status=job.status,
            kernel_name=job.kwargs["kernel_name"],
            source=job.kwargs["ipynb"] if include_source else None,
            self_url=request.url_for("get_nbexec_job", job_id=job.id),
            start_time=job_result.start_time if job_result else None,
            finish_time=job_result.finish_time if job_result else None,
            success=job_result.success if job_result else None,
            ipynb=job_result.result if job_result else None,
        )


class PostNotebookRequest(BaseModel):
    """The ``POST /notebooks/`` request body."""

    ipynb: Union[str, Dict[str, Any]]
    """The contents of a Jupyter notebook. If a string, the conttent is parsed
    as JSON. Alternatively, the content can be submitted pre-pared as an
    object.
    """

    kernel_name: str = "LSST"
    """The name of the Jupyter kernel to execute this by."""

    def get_ipynb_as_str(self) -> str:
        if isinstance(self.ipynb, str):
            return self.ipynb
        else:
            return json.dumps(self.ipynb)
