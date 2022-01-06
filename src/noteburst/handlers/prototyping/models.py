"""JSON message models for the prototype API."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from arq.jobs import JobStatus
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    import arq.jobs


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


class QueuedJob(BaseModel):
    """A resource with info about an arq job."""

    job_id: str
    """The arq job ID."""

    task_name: str

    enqueue_time: datetime

    start_time: Optional[datetime]

    finish_time: Optional[datetime]

    success: Optional[bool]

    status: JobStatus

    @classmethod
    async def from_job(cls, job: arq.jobs.Job) -> QueuedJob:
        job_info = await job.info()
        result_info = await job.result_info()
        job_status = await job.status()
        return cls(
            job_id=job.job_id,
            task_name=job_info.function,
            enqueue_time=job_info.enqueue_time,
            start_time=result_info.start_time if result_info else None,
            finish_time=result_info.finish_time if result_info else None,
            success=result_info.success if result_info else None,
            status=job_status,
        )
