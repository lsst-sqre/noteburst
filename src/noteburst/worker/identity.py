"""Management of Science Platform user identitity for workers.

Each noteburst worker runs under a unique Science Platform user account. The
account is aquired through a redis-based lock.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import structlog
import yaml
from aioredlock import Aioredlock, Lock, LockError
from pydantic import BaseModel

from noteburst.config import WorkerConfig


class IdentityModel(BaseModel):
    """Model for a single user identity in the IdentityConfigModel-based
    configuration file.
    """

    username: str
    """The username of the user account."""

    uid: str
    """The UID of the user account."""


class IdentityConfigModel(BaseModel):

    __root__: List[IdentityModel]

    @classmethod
    def from_yaml(cls, path: Path) -> IdentityConfigModel:
        data = yaml.safe_load(path.read_text())
        return cls.parse_obj(data)


@dataclass
class IdentityClaim:
    """A claimed user identity that holds a lock from the IdentityManager."""

    username: str
    """The username of the user account."""

    uid: str
    """The UID of the user account."""

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

    Parmaeters
    ----------
    lock_manager : `aioredlock.Aioredlock`
        The lock manager
    identities : list of `IdentityModel`
        The parsed identity pool configuration file.
    """

    def __init__(
        self,
        *,
        lock_manager: Aioredlock,
        identities: List[IdentityModel],
    ) -> None:
        self.lock_manager = lock_manager
        self.identities = identities
        self._current_identity: Optional[IdentityClaim] = None
        self._logger = structlog.get_logger(__name__)

    @classmethod
    def from_config(cls, config: WorkerConfig) -> IdentityManager:
        """Create an IdentityManager from a configuration instance.

        Parameters
        ----------
        config : `noteburst.config.WorkerConfig`
            The worker configuration.

        Returns
        -------
        `IdentityManager`
            The identity manager instance.
        """
        lock_manager = Aioredlock(config.aioredlock_redis_config)

        identities = [
            identity
            for identity in IdentityConfigModel.from_yaml(
                config.identities_path
            ).__root__
        ]

        return cls(lock_manager=lock_manager, identities=identities)

    async def close(self) -> None:
        """Release any claimed identity and connection to Redis."""
        if self._current_identity is not None:
            await self._current_identity.release()
            self._current_identity = None
            self._logger.info("Released worker user identity")
        await self.lock_manager.destroy()
        self._logger.info("Shut down identity manager")

    async def get_identity(self) -> IdentityClaim:
        """Get a unique identity (either claiming a new identity or providing
        the already-claimed identity).

        This identity is claimed through the Redis lock.

        Returns
        -------
        `IdentityClaim`
            Information about the Science Platform identity.
        """
        if self._current_identity:
            if self._current_identity.valid:
                return self._current_identity
            else:
                self._current_identity = None

        for identity in self.identities:
            try:
                # We don't set the timeout argument on lock; in doing so we
                # use aioredlock's built-in watchdog that renews locks.
                lock = await self.lock_manager.lock(identity.uid)
            except LockError:
                self._logger.debug(
                    "Identity already claimed", username=identity.username
                )
                continue

            self._logger.info("Claimed identity", username=identity.username)
            self._current_identity = IdentityClaim(
                username=identity.username, uid=identity.uid, lock=lock
            )
            return self._current_identity

        raise IdentityClaimError(
            "Could not claim an Science Platform identity (none available)."
        )
