"""Configuration definition."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated, Self

from arq.connections import RedisSettings
from pydantic import Field, HttpUrl, RedisDsn, SecretStr, model_validator
from pydantic_settings import BaseSettings
from safir.arq import ArqMode
from safir.logging import LogLevel, Profile
from safir.metrics import MetricsConfiguration, metrics_configuration_factory

__all__ = [
    "Config",
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


class Config(BaseSettings):
    """Noteburst app configuration."""

    name: Annotated[str, Field(alias="SAFIR_NAME")] = "Noteburst"

    profile: Annotated[Profile, Field(alias="SAFIR_PROFILE")] = (
        Profile.production
    )

    log_level: Annotated[LogLevel, Field(alias="SAFIR_LOG_LEVEL")] = (
        LogLevel.INFO
    )

    logger_name: Annotated[
        str,
        Field(
            description=(
                "The root name of the Python logger, which is also the name "
                "of the root Python module"
            )
        ),
    ] = "noteburst"

    path_prefix: Annotated[
        str,
        Field(
            "/noteburst",
            alias="NOTEBURST_PATH_PREFIX",
            description="The URL path prefix where noteburst is hosted.",
        ),
    ] = "/noteburst"

    metrics: Annotated[
        MetricsConfiguration,
        Field(
            default_factory=metrics_configuration_factory,
            title="Metrics configuration",
        ),
    ]

    environment_url: Annotated[
        HttpUrl,
        Field(
            alias="NOTEBURST_ENVIRONMENT_URL",
            description=(
                "The base URL of the Rubin Science Platform environment. This "
                "is used for creating URLs to services, such as JupyterHub."
            ),
        ),
    ]

    jupyterhub_path_prefix: Annotated[
        str,
        Field(
            alias="NOTEBURST_JUPYTERHUB_PATH_PREFIX",
            description="The path prefix for the JupyterHub service.",
        ),
    ] = "/nb/"

    nublado_controller_path_prefix: Annotated[
        str,
        Field(
            alias="NOTEBURST_NUBLADO_CONTROLLER_PATH_PREFIX",
            description="The path prefix for the Nublado controller service.",
        ),
    ] = "/nublado"

    gafaelfawr_token: Annotated[
        SecretStr,
        Field(
            alias="NOTEBURST_GAFAELFAWR_TOKEN",
            description=(
                "This token is used to make an admin API call to Gafaelfawr "
                "to get a token for the user."
            ),
        ),
    ]

    redis_url: Annotated[
        RedisDsn,
        Field(
            alias="NOTEBURST_REDIS_URL",
            # Preferred by mypy over a string default
            default_factory=lambda: RedisDsn("redis://localhost:6379/1"),
            description=(
                "URL for the redis instance, used by the worker queue.",
            ),
        ),
    ]

    arq_mode: Annotated[
        ArqMode,
        Field(
            alias="NOTEBURST_ARQ_MODE",
            description=(
                "The Arq mode. Use 'test' to mock arq/redis for testing."
            ),
        ),
    ] = ArqMode.production

    slack_webhook_url: Annotated[
        HttpUrl | None,
        Field(
            alias="NOTEBURST_SLACK_WEBHOOK_URL",
            description=(
                "Webhook URL for sending error messages to a Slack channel."
            ),
        ),
    ] = None

    sentry_traces_sample_rate: Annotated[
        float,
        Field(
            default=0,
            alias="NOTEBURST_SENTRY_TRACES_SAMPLE_RATE",
            description=(
                "If Sentry is enabled (by providing a SENTRY_DSN env var"
                "value), this is a number between 0 and 1 that is a percentage"
                "of the number of requests that are traced."
            ),
            ge=0,
            le=1,
        ),
    ]

    @property
    def arq_redis_settings(self) -> RedisSettings:
        """Create a Redis settings instance for arq."""
        return RedisSettings(
            host=self.redis_url.host or "localhost",
            port=self.redis_url.port or 6379,
            database=(
                int(self.redis_url.path.lstrip("/"))
                if self.redis_url.path
                else 0
            ),
        )


class WorkerConfig(Config):
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


config = Config()
"""Configuration for noteburst."""
