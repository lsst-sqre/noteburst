"""Logging a client into the Rubin Science Platform."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional

from noteburst.config import config

if TYPE_CHECKING:
    import httpx.Client

__all__ = ["User", "AuthenticatedUser"]


@dataclass
class User:
    """A Rubin Science Platform user.

    To create a user that is logged into the RSP, use
    `User.login`, which returns a new `AuthenticatedUser` instance.
    """

    username: str
    """The user's username."""

    uid: Optional[str]
    """The user's UID.

    This can be set as `None` if the authentication services provides the UID.
    """

    async def login(
        self, *, scopes: List[str], http_client: httpx.AsyncClient
    ) -> AuthenticatedUser:
        return await AuthenticatedUser.create(
            username=self.username,
            uid=self.uid,
            scopes=scopes,
            http_client=http_client,
        )


@dataclass
class AuthenticatedUser(User):
    """A user authenticated with a token."""

    scopes: List[str]
    """The token's scopes (example: ``["exec:notebook", "read:tap"]``."""

    token: str
    """The user's authentication token."""

    @classmethod
    async def create(
        cls,
        *,
        username: str,
        uid: Optional[str],
        scopes: List[str],
        http_client: httpx.AsyncClient,
    ) -> AuthenticatedUser:
        """Create an authenticated user by logging into the Science Platform.

        Parameters
        ----------
        username : `str`
            The username.
        uid : `str` or `None`
            The user's UID. This can be `None` if the authentication service
            assigns the UID.
        scopes : `list` of `str`
            The scopes the user's token should possess.
        http_client : httpx.Client
            The httpx client session.
        """
        token_url = f"{config.environment_url}/auth/api/v1/tokens"
        token_request_data = {
            "username": username,
            "name": "Noteburst",
            "token_type": "user",
            "token_name": f"noteburst {str(float(time.time()))}",
            "scopes": scopes,
            "expires": int(time.time() + 2419200),
        }
        if uid:
            token_request_data["uid"] = uid
        r = await http_client.post(
            token_url,
            headers={
                "Authorization": (
                    f"Bearer {config.gafaelfawr_token.get_secret_value()}"
                )
            },
            json=token_request_data,
        )
        r.raise_for_status()
        body = r.json()
        return cls(
            username=username,
            uid=uid,
            token=body["token"],
            scopes=scopes,
        )
