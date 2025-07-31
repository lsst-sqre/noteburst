"""Management of Science Platform user identity for workers.

Each noteburst worker runs under a unique Science Platform user account. The
account is acquired through a redis-based lock.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, Field, RootModel

from noteburst.config.worker import WorkerConfig


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


class IdentityClaimError(Exception):
    """An error related to claiming an identity for the worker."""


def get_identity(config: WorkerConfig) -> IdentityModel:
    """Return an RSP identity from list in a file with an env var index.

    Parameters
    ----------
    config
        The worker configuration.

    Raises
    ------
    IdentityClaimError
        When an identity can not be found.
    """
    try:
        identities = IdentityConfigModel.from_yaml(config.identities_path).root
    except Exception as e:
        raise IdentityClaimError("Error reading identities file") from e

    index = config.identity_index
    try:
        identity = identities[index]
    except IndexError as e:
        msg = f"No identity for index: {index} in identities: {identities}"
        raise IdentityClaimError(msg) from e

    return identity
