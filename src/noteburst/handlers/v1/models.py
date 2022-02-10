"""JSON message models for the /v1/ API endpoints."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional, Union

from arq.jobs import JobStatus
from fastapi import Request
from pydantic import AnyHttpUrl, BaseModel

from noteburst.dependencies.arqpool import JobMetadata, JobResult


class NbexecJobBase(BaseModel):
    """Base model for info about a notebook execution job."""

    job_id: str
    """The arq job ID."""

    kernel_name: str
    """Name of the kernel the notebook is executed with."""

    enqueue_time: datetime
    """Time when the job was added to the queue (UTC)."""

    status: JobStatus
    """The current status of the notebook execution job."""

    self_url: AnyHttpUrl
    """The URL of this resource."""


class QueuedNbexecJob(NbexecJobBase):
    """A resource with info about an nbexec job."""

    ipynb: Optional[str] = None
    """The content of the source ipynb file (JSON-encoded string)."""

    result_url: Optional[AnyHttpUrl] = None
    """The URL for the result."""

    @classmethod
    async def from_job_metadata(
        cls, *, job: JobMetadata, request: Request, include_ipynb: bool = False
    ) -> QueuedNbexecJob:
        return cls(
            job_id=job.id,
            enqueue_time=job.enqueue_time,
            status=job.status,
            kernel_name=job.kwargs["kernel_name"],
            ipynb=job.kwargs["ipynb"] if include_ipynb else None,
            self_url=request.url_for("get_nbexec_job", job_id=job.id),
            result_url=request.url_for("get_nbexec_job_result", job_id=job.id),
        )


class QueuedNbexecJobResult(NbexecJobBase):
    """A resource with info about an nbexec job."""

    start_time: datetime
    """Time when the job started (UTC)."""

    finish_time: datetime
    """Time when the job completed (UTC)."""

    success: bool
    """Whether the execution was successful or not."""

    ipynb: str
    """The contents of the executed Jupyter notebook."""

    @classmethod
    async def from_job_result(
        cls, *, job: JobResult, request: Request
    ) -> QueuedNbexecJobResult:
        return cls(
            job_id=job.id,
            enqueue_time=job.enqueue_time,
            status=job.status,
            kernel_name=job.kwargs["kernel_name"],
            self_url=request.url_for("get_nbexec_job_result", job_id=job.id),
            start_time=job.start_time,
            finish_time=job.finish_time,
            success=job.success,
            ipynb=job.result,  # output of nbexec is the ipynb string
        )


class PostNbexecRequest(BaseModel):
    """The ``POST /nbexec`` request body."""

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
