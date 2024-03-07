"""Exceptions for the Noteburst application."""

from __future__ import annotations

from typing import Self

from fastapi import status
from safir.fastapi import ClientRequestError

__all__ = ["TaskError", "NbexecTaskError", "NoteburstClientRequestError"]


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


class NoteburstClientRequestError(ClientRequestError):
    """Error related to the API client."""


class JobNotFoundError(NoteburstClientRequestError):
    """Error raised when a notebook execution job is not found."""

    error = "unknown_job"
    status_code = status.HTTP_404_NOT_FOUND
