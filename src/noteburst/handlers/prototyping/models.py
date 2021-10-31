"""JSON message models for the prototype API."""

from pydantic import BaseModel, Field


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
