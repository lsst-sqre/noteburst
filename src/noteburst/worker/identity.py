"""Management of Science Platform user identity for workers.

Each noteburst worker runs under a unique Science Platform user account. The
account is acquired through a redis-based lock.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import yaml
from aioredlock import Aioredlock, Lock, LockError
from pydantic import BaseModel, Field, RootModel
from structlog.stdlib import BoundLogger

from noteburst.config import WorkerConfig


class IdentityModel(BaseModel):
    """Model for a single user identity in the IdentityConfigModel-based
    configuration file.
    """

    username: Annotated[
        str, Field(description="The username of the user account.")
    ]

    uid: Annotated[
        int | None,
        Field(
            description=(
                "The UID of the user account. This can be `None` if the "
                "authentication system assigns the UID."
            )
        ),
    ] = None

    gid: Annotated[
        int | None,
        Field(
            description=(
                "The GID of the user account. This can be `None` if the "
                "authentication system assigns the GID."
            )
        ),
    ] = None


class IdentityConfigModel(RootModel):
    """Model for the IdentityConfigModel-based configuration file."""

    root: list[IdentityModel]

    @classmethod
    def from_yaml(cls, path: Path) -> IdentityConfigModel:
        data = yaml.safe_load(path.read_text())
        return cls.model_validate(data)


@dataclass
class IdentityClaim:
    """A claimed user identity that holds a lock from the IdentityManager."""

    username: str
    """The username of the user account."""

    uid: int | None
    """The UID of the user account."""

    gid: int | None
    """The GID of the user account."""

    lock: Lock
    """The aioredlock lock that this claim holds."""

    @property
    def valid(self) -> bool:
        return self.lock.valid

    async def release(self) -> None:
        await self.lock.release()


class IdentityClaimError(Exception):
    """An error related to claiming an identity for the worker."""


class IdentityManager:
    """A manager that provides a unique Science Platform user identity, claimed
    in a Redis-based global lock, from a pool of possible identities from the
    app configuration.

    Create an IdentityManager instance via the `IdentityManager.from_config`
    class method. Once initialized, call the `IdentityManager.get_identity`
    method to claim an identity, or obtain the already-claimed identity.

    Parameters
    ----------
    lock_manager
        The lock manager
    identities
        The parsed identity pool configuration file.
    """

    def __init__(
        self,
        *,
        lock_manager: Aioredlock,
        identities: list[IdentityModel],
        logger: BoundLogger,
    ) -> None:
        self.lock_manager = lock_manager
        self.identities = identities
        self._current_identity: IdentityClaim | None = None
        self._logger = logger

    @classmethod
    def from_config(
        cls, *, config: WorkerConfig, logger: BoundLogger
    ) -> IdentityManager:
        """Create an IdentityManager from a configuration instance.

        Parameters
        ----------
        config
            The worker configuration.

        Returns
        -------
        IdentityManager
            The identity manager instance.
        """
        lock_manager = Aioredlock(config.aioredlock_redis_config)

        identities = list(
            IdentityConfigModel.from_yaml(config.identities_path).root
        )

        return cls(
            lock_manager=lock_manager, identities=identities, logger=logger
        )

    async def close(self) -> None:
        """Release any claimed identity and connection to Redis."""
        await self._release_identity()
        await self.lock_manager.destroy()
        self._logger.info("Shut down identity manager")

    async def _release_identity(self) -> None:
        if self._current_identity is not None:
            await self._current_identity.release()
            self._current_identity = None
            self._logger.info("Released worker user identity")

    async def get_identity(
        self, _identities: list[IdentityModel] | None = None
    ) -> IdentityClaim:
        """Get a unique identity (either claiming a new identity or providing
        the already-claimed identity).

        This identity is claimed through the Redis lock.

        Returns
        -------
        IdentityClaim
            Information about the Science Platform identity.
        """
        identities = _identities if _identities else self.identities

        if self._current_identity:
            if self._current_identity.valid:
                return self._current_identity
            else:
                self._current_identity = None

        for identity in identities:
            try:
                # We don't set the timeout argument on lock; in doing so we
                # use aioredlock's built-in watchdog that renews locks.
                lock = await self.lock_manager.lock(identity.username)
            except LockError:
                self._logger.debug(
                    "Identity already claimed", username=identity.username
                )
                continue

            self._logger.info("Claimed identity", username=identity.username)
            self._current_identity = IdentityClaim(
                username=identity.username,
                uid=identity.uid,
                gid=identity.gid,
                lock=lock,
            )
            return self._current_identity

        raise IdentityClaimError(
            "Could not claim an Science Platform identity (none available)."
        )

    async def get_next_identity(
        self, prev_identity: IdentityClaim | None = None
    ) -> IdentityClaim:
        """Get the next available identity if the existing identity claim
        did not result in a successful JupyterLab launch.

        If a worker exits and the JupyterLab pod does not successfully close,
        it becomes orphaned. If a new worker picks up the identity of the
        orphaned JupyterLab pod, its start-up sequence will fail. This method
        provides a way for the worker to try the next available identity in
        that circumstance.

        Parameters
        ----------
        prev_identity
            The previously claimed identity, or None if this is the initial
            claim.

        Returns
        -------
        IdentityClaim
            The newly claimed identity.

        Raises
        ------
        IdentityClaimError
            When no identity can be claimed.
        """
        if self._current_identity is not None:
            await self._release_identity()

        # If prev_identity is None, start from the beginning of the identity
        # list
        if prev_identity is None:
            return await self.get_identity()

        for i, identity in enumerate(self.identities):
            # Find the same identity as before to then get the next one
            if identity.username != prev_identity.username:
                continue

            if i + 1 >= len(self.identities):
                raise IdentityClaimError(
                    "Could not claim an Science Platform identity (none "
                    "available)."
                )

            return await self.get_identity(
                _identities=self.identities[i + 1 :]
            )

        raise IdentityClaimError(
            "Could not claim an Science Platform identity (none available)."
        )
