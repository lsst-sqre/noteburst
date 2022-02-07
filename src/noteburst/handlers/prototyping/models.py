"""JSON message models for the prototype API."""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional, Union

from arq.jobs import JobStatus
from pydantic import AnyHttpUrl, BaseModel, Field

if TYPE_CHECKING:
    from fastapi import Request

    from noteburst.dependencies.arqpool import JobMetadata, JobResult


class PostLoginRequest(BaseModel):
    """The ``POST /login`` request body."""

    username: str
    """Username of the user to log in."""

    uid: str
    """The user's UID.

    Get this from the ``GET /auth/api/v1/user-info`` endpoint in an
    authenticated browser session, in the ``uid`` response field.
    """


class PostCodeRequest(BaseModel):
    """The ``POST /code`` request body."""

    username: str
    """Username of the user to log in."""

    uid: str
    """The user's UID.

    Get this from the ``GET /auth/api/v1/user-info`` endpoint in an
    authenticated browser session, in the ``uid`` response field.
    """

    code: str = Field('print("hello world")')
    """A Python code snippet to execute."""


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


class PostRunPythonRequest(BaseModel):
    """The ``POST /runpython`` request body."""

    py: str
    """Python code to execute."""

    kernel_name: str = "LSST"
    """The name of the Jupyter kernel to execute this by."""
