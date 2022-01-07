"""JSON message models for the prototype API."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from arq.jobs import JobStatus
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from noteburst.dependencies.arqpool import JobMetadata


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

    status: JobStatus

    @classmethod
    async def from_job_metadata(cls, meta: JobMetadata) -> QueuedJob:
        return cls(
            job_id=meta.id,
            task_name=meta.name,
            enqueue_time=meta.enqueue_time,
            status=meta.status,
        )
