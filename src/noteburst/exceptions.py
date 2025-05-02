"""Exceptions for the Noteburst application."""

from __future__ import annotations

from typing import Any, Self

from fastapi import status
from safir.fastapi import ClientRequestError
from safir.sentry import SentryException
from safir.slack.blockkit import SlackException, SlackMessage, SlackTextField

__all__ = [
    "NbexecTaskError",
    "NbexecTaskTimeoutError",
    "NoteburstClientRequestError",
    "NoteburstError",
    "NoteburstWorkerError",
    "TaskError",
]


class NoteburstWorkerError(SentryException):
    """Base class for Noteburst worker exceptions.

    Exceptions are reported to Sentry.
    """

    def __init__(
        self,
        msg: str,
        tags: dict[str, str] | None = None,
        contexts: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(msg)
        if tags:
            self.tags = tags
        if contexts:
            self.contexts = contexts


class TaskError(Exception):
    """Error related to Arq task execution."""

    task_name: str = "unknown"
    """The name of the Arq task that raised the exception."""

    # Arq doesn't seem to support exceptions in tasks that have multiple
    # arguments. Our strategy here is to use from_exception to create a single
    # message string for the exception so that arq itself only needs to
    # serialize a single string argument to the exception.

    @classmethod
    def from_exception(cls, exc: Exception) -> Self:
        return cls(f"{cls.task_name} task error\n\n{exc!s}")


class NbexecTaskError(TaskError):
    """Error related to a notebook execution task (nbexec)."""

    task_name = "nbexec"


class NbexecTaskTimeoutError(NbexecTaskError):
    """Error raised when a notebook execution task times out."""

    @classmethod
    def from_exception(cls, exc: Exception) -> Self:
        return cls(f"{cls.task_name} timeout error\n\n{exc!s}")


class NoteburstClientRequestError(ClientRequestError):
    """Error related to the API client."""


class JobNotFoundError(NoteburstClientRequestError):
    """Error raised when a notebook execution job is not found."""

    error = "unknown_job"
    status_code = status.HTTP_404_NOT_FOUND


class NoteburstError(SlackException):
    """Base class for internal Noteburst exceptions on the FastAPI side.

    This exception derives from SlackException so that uncaught internal
    exceptions are reported to Slack.
    """


class NoteburstJobError(NoteburstError):
    """Error related to a notebook execution job."""

    def __init__(self, msg: str, *, user: str | None, job_id: str) -> None:
        super().__init__(msg, user=user)
        self.job_id = job_id

    def to_slack(self) -> SlackMessage:
        message = super().to_slack()
        message.fields.append(
            SlackTextField(heading="Job ID", text=self.job_id)
        )
        return message
