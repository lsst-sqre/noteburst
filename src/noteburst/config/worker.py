"""Config for the Noteburst worker."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated, Self, assert_never

from pydantic import Field, RedisDsn, model_validator
from rubin.nublado.client.models import (
    NubladoImage,
    NubladoImageByClass,
    NubladoImageByReference,
    NubladoImageClass,
)

from .frontend import FrontendConfig

__all__ = [
    "JupyterImageSelector",
    "WorkerConfig",
    "WorkerKeepAliveSetting",
]


class JupyterImageSelector(str, Enum):
    """Possible ways of selecting a JupyterLab image."""

    recommended = "recommended"
    """Currently recommended image."""

    weekly = "weekly"
    """Current weekly image."""

    reference = "reference"
    """Select a specific image by reference."""


class WorkerKeepAliveSetting(str, Enum):
    """Modes for the worker keep-alive function."""

    disabled = "disabled"
    """Do not run a keep-alive function."""

    fast = "fast"
    """Run the keep-alive function at a high frequency (every 30 seconds)."""

    normal = "normal"
    """Run the keep-alive function at a slower frequency (i.e. 5 minutes)."""

    hourly = "hourly"
    """Run the keep-alive function every hour."""

    daily = "daily"
    """Run the keep-alive function at a very slow frequency (i.e. 24 hours)."""


class WorkerConfig(FrontendConfig):
    """Configuration superset for arq worker processes."""

    identities_path: Annotated[
        Path,
        Field(
            alias="NOTEBURST_WORKER_IDENTITIES_PATH",
            description=(
                "Path to the configuration file with the pool of Science "
                "Platform identities available to workers."
            ),
        ),
    ]

    identity_index: Annotated[
        int,
        Field(
            alias="NOTEBURST_IDENTITY_INDEX",
            description=(
                "The index of the identity in the identities list to use."
            ),
        ),
    ]

    queue_name: Annotated[
        str,
        Field(
            alias="NOTEBURST_WORKER_QUEUE_NAME",
            description=(
                "Name of the arq queue that the worker processes from."
            ),
        ),
    ] = "arq:queue"

    identity_lock_redis_url: Annotated[
        RedisDsn,
        Field(
            alias="NOTEBURST_WORKER_LOCK_REDIS_URL",
            # Preferred by mypy over a string default
            default_factory=lambda: RedisDsn("redis://localhost:6379/1"),
            description=(
                "URL for the redis instance, used by the worker to lock "
                "JupyterLab user identities to a worker instance."
            ),
        ),
    ]

    job_timeout: Annotated[
        int,
        Field(
            alias="NOTEBURST_WORKER_JOB_TIMEOUT",
            description=(
                "The timeout, in seconds, for a job until it is timed out."
            ),
        ),
    ] = 300

    max_concurrent_jobs: Annotated[
        int,
        Field(
            alias="NOTEBURST_WORKER_MAX_CONCURRENT_JOBS",
            description=(
                "The maximum number of concurrent jobs a worker can handle. "
                "This should be equal to less than the number of CPUs on the "
                "JupyterLab pod."
            ),
        ),
    ] = 3

    worker_token_lifetime: Annotated[
        int,
        Field(
            alias="NOTEBURST_WORKER_TOKEN_LIFETIME",
            description="Worker auth token lifetime in seconds.",
        ),
    ] = 2419200

    worker_token_scopes: Annotated[
        str,
        Field(
            alias="NOTEBURST_WORKER_TOKEN_SCOPES",
            description=(
                "Worker (nublado pod) token scopes as a comma-separated "
                "string."
            ),
        ),
    ] = "exec:notebook"

    image_selector: Annotated[
        JupyterImageSelector,
        Field(
            alias="NOTEBURST_WORKER_IMAGE_SELECTOR",
            description="Method for selecting a Jupyter image to run.",
        ),
    ] = JupyterImageSelector.recommended

    image_reference: Annotated[
        str | None,
        Field(
            alias="NOTEBURST_WORKER_IMAGE_REFERENCE",
            description=(
                "Docker image reference, if NOTEBURST_WORKER_IMAGE_SELECTOR "
                "is ``reference``."
            ),
        ),
    ] = None

    worker_keepalive: Annotated[
        WorkerKeepAliveSetting,
        Field(
            alias="NOTEBURST_WORKER_KEEPALIVE",
            description=(
                "Keep-alive setting for the worker process. This setting "
                "must be fast enough to defeat the Nublado pod culler."
            ),
        ),
    ] = WorkerKeepAliveSetting.normal

    @property
    def aioredlock_redis_config(self) -> list[str]:
        """Redis configurations for aioredlock."""
        return [str(self.identity_lock_redis_url)]

    @model_validator(mode="after")
    def is_image_ref_set(self) -> Self:
        """Validate that image_reference is set if image_selector is
        set to reference.
        """
        if (
            self.image_reference is None
            and self.image_selector == JupyterImageSelector.reference
        ):
            raise ValueError(
                "Set NOTEBURST_WORKER_IMAGE_REFERENCE since "
                "NOTEBURST_WORKER_IMAGE_SELECTOR is ``reference``."
            )

        return self

    @property
    def parsed_worker_token_scopes(self) -> list[str]:
        """Sequence of worker token scopes, parsed from the comma-separated
        list in `worker_token_scopes`.
        """
        return [t.strip() for t in self.worker_token_scopes.split(",") if t]

    @property
    def nublado_image(self) -> NubladoImage:
        """The JupyterLab image to use for the pod."""
        match self.image_selector:
            case JupyterImageSelector.recommended:
                return NubladoImageByClass(
                    image_class=NubladoImageClass.RECOMMENDED
                )
            case JupyterImageSelector.weekly:
                return NubladoImageByClass(
                    image_class=NubladoImageClass.LATEST_WEEKLY
                )
            case JupyterImageSelector.reference:
                return NubladoImageByReference(reference=self.image_reference)
            case _:
                assert_never(self.image_selector)
