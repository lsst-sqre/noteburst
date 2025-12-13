"""RSP and Nublado users."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Self

from rubin.gafaelfawr import GafaelfawrClient

from noteburst.config.frontend import config

__all__ = ["AuthenticatedUser", "User"]


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
        gafaelfawr_client: GafaelfawrClient,
        token_lifetime: int,
    ) -> AuthenticatedUser:
        return await AuthenticatedUser.create(
            username=self.username,
            uid=self.uid,
            gid=self.gid,
            scopes=scopes,
            gafaelfawr_client=gafaelfawr_client,
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
        gafaelfawr_client: GafaelfawrClient,
        lifetime: int,
    ) -> Self:
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
        gafaelafwr_client
            Shared Gafaelfawr client.
        lifetime
            The lifetime of the authentication token, in seconds.
        """
        token = await gafaelfawr_client.create_service_token(
            config.gafaelfawr_token.get_secret_value(),
            username=username,
            name="Noteburst",
            uid=uid,
            gid=gid,
            scopes=scopes,
            expires=datetime.now(tz=UTC) + timedelta(seconds=lifetime),
        )
        return cls(
            username=username,
            uid=uid,
            gid=gid,
            token=token,
            scopes=scopes,
        )
