"""JSON message models for the /v1/ API endpoints."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional, Union

from arq.jobs import JobStatus
from fastapi import Request
from pydantic import AnyHttpUrl, BaseModel

from noteburst.dependencies.arqpool import JobMetadata, JobResult


class QueuedJobBase(BaseModel):
    """Base model for info about an arq job."""

    job_id: str
    """The arq job ID."""

    task_name: str

    enqueue_time: datetime

    status: JobStatus

    self_url: AnyHttpUrl


class QueuedJob(QueuedJobBase):
    """A resource with info about an arq job."""

    result_url: Optional[AnyHttpUrl] = None

    @classmethod
    async def from_job_metadata(
        cls, *, job: JobMetadata, request: Request
    ) -> QueuedJob:
        return cls(
            job_id=job.id,
            task_name=job.name,
            enqueue_time=job.enqueue_time,
            status=job.status,
            self_url=request.url_for("get_job", job_id=job.id),
            result_url=request.url_for("get_job_result", job_id=job.id),
        )


class QueuedJobResult(QueuedJobBase):
    """A resource with info about an arq job."""

    start_time: datetime

    finish_time: datetime

    success: bool

    result: Any

    @classmethod
    async def from_job_result(
        cls, *, job: JobResult, request: Request
    ) -> QueuedJobResult:
        return cls(
            job_id=job.id,
            task_name=job.name,
            enqueue_time=job.enqueue_time,
            status=job.status,
            self_url=request.url_for("get_job_result", job_id=job.id),
            start_time=job.start_time,
            finish_time=job.finish_time,
            success=job.success,
            result=job.result,
        )


class PostNbexecRequest(BaseModel):
    """The ``POST /nbexec`` request body."""

    ipynb: Union[str, Dict[str, Any]]
    """The contents of a Jupyter notebook."""

    kernel_name: str = "LSST"
    """The name of the Jupyter kernel to execute this by."""

    def get_ipynb_as_str(self) -> str:
        if isinstance(self.ipynb, str):
            return self.ipynb
        else:
            return json.dumps(self.ipynb)
