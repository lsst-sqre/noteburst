"""Logging a client into the Rubin Science Platform."""

from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx

from noteburst.config import config

__all__ = ["User", "AuthenticatedUser"]


@dataclass
class User:
    """A Rubin Science Platform user.

    To create a user that is logged into the RSP, use
    `User.login`, which returns a new `AuthenticatedUser` instance.
    """

    username: str
    """The user's username."""

    uid: int | None
    """The user's UID.

    This can be set as `None` if the authentication services provides the UID.
    """

    gid: int | None
    """The user's GID.

    This can be set as `None` if the authentication services provides the GID.
    """

    async def login(
        self,
        *,
        scopes: list[str],
        http_client: httpx.AsyncClient,
        token_lifetime: int,
    ) -> AuthenticatedUser:
        return await AuthenticatedUser.create(
            username=self.username,
            uid=self.uid,
            gid=self.gid,
            scopes=scopes,
            http_client=http_client,
            lifetime=token_lifetime,
        )


@dataclass
class AuthenticatedUser(User):
    """A user authenticated with a token."""

    scopes: list[str]
    """The token's scopes (example: ``["exec:notebook", "read:tap"]``."""

    token: str
    """The user's authentication token."""

    @classmethod
    async def create(
        cls,
        *,
        username: str,
        uid: int | None,
        gid: int | None,
        scopes: list[str],
        http_client: httpx.AsyncClient,
        lifetime: int,
    ) -> AuthenticatedUser:
        """Create an authenticated user by logging into the Science Platform.

        Parameters
        ----------
        username
            The username.
        uid
            The user's UID. This can be `None` if the authentication service
            assigns the UID.
        gid
            The user's GID. This can be `None` if the authentication service
            assigns the GID.
        scopes
            The scopes the user's token should possess.
        http_client
            The httpx client session.
        lifetime
            The lifetime of the authentication token, in seconds.
        """
        token_url = urljoin(str(config.environment_url), "/auth/api/v1/tokens")
        token_request_data = {
            "username": username,
            "name": "Noteburst",
            "token_type": "service",
            "token_name": f"noteburst {float(time.time())!s}",
            "scopes": scopes,
            "expires": int(time.time() + lifetime),
        }
        if uid:
            token_request_data["uid"] = uid
        if gid:
            token_request_data["gid"] = gid
        r = await http_client.post(
            token_url,
            headers={
                "Authorization": (
                    f"Bearer {config.gafaelfawr_token.get_secret_value()}"
                )
            },
            json=token_request_data,
        )
        print(r.json())  # noqa: T201
        r.raise_for_status()
        body = r.json()
        return cls(
            username=username,
            uid=uid,
            gid=gid,
            token=body["token"],
            scopes=scopes,
        )
