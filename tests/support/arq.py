"""Test helpers for the arq queue."""

from __future__ import annotations

from dataclasses import dataclass

from noteburst.worker.identity import IdentityClaimError


@dataclass
class MockIdentityClaim:
    """A mock version of IdentityClaim for tests (does not have a working lock
    attribute.
    """

    username: str
    """The username of the user account."""

    uuid: str
    """The UUID of the user account."""

    valid: bool = True
    """Whether the lock is in place, or not."""

    async def release(self) -> None:
        pass


class MockIdentityManager:
    """A mock of the identity manager for use in test arq worker contexts.

    This is a partial mock of IdentityManager that namely provides the
    ``get_identity`` method.
    """

    def __init__(self) -> None:
        self._current_identity: MockIdentityClaim | None = None

    async def get_identity(self) -> MockIdentityClaim:
        if self._current_identity:
            return self._current_identity
        else:
            raise IdentityClaimError(
                "Could not claim an Science Platform identity "
                "(none available)."
            )

    def set_identity_test(self, identity_claim: MockIdentityClaim) -> None:
        """Test helper method for setting the mock manager's current identity.

        Parameters
        ----------
        identity_claim : `MockIdentityClaim`
            The identity.
        """
        self._current_identity = identity_claim
