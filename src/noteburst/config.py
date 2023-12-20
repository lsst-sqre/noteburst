"""Configuration definition."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Optional

from arq.connections import RedisSettings
from pydantic import Field, HttpUrl, RedisDsn, SecretStr, validator
from pydantic_settings import BaseSettings
from safir.arq import ArqMode
from safir.logging import LogLevel, Profile

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
    name: str = Field("Noteburst", alias="SAFIR_NAME")

    profile: Profile = Field(Profile.production, alias="SAFIR_PROFILE")

    log_level: LogLevel = Field(LogLevel.INFO, alias="SAFIR_LOG_LEVEL")

    logger_name: str = "noteburst"
    """The root name of the Python logger, which is also the name of the
    root Python module.
    """

    path_prefix: str = Field("/noteburst", alias="NOTEBURST_PATH_PREFIX")
    """The URL path prefix where noteburst is hosted."""

    environment_url: HttpUrl = Field(alias="NOTEBURST_ENVIRONMENT_URL")
    """The base URL of the Rubin Science Platform environment.

    This is used for creating URLs to services, such as JupyterHub.
    """

    jupyterhub_path_prefix: str = Field(
        "/nb/",
        alias="NOTEBURST_JUPYTERHUB_PATH_PREFIX",
        description="The path prefix for the JupyterHub service.",
    )

    nublado_controller_path_prefix: str = Field(
        "/nublado",
        alias="NOTEBURST_NUBLADO_CONTROLLER_PATH_PREFIX",
        description="The path prefix for the Nublado controller service.",
    )

    gafaelfawr_token: SecretStr = Field(alias="NOTEBURST_GAFAELFAWR_TOKEN")
    """This token is used to make an admin API call to Gafaelfawr to get a
    token for the user.
    """

    redis_url: RedisDsn = Field(
        alias="NOTEBURST_REDIS_URL",
        # Preferred by mypy over a string default
        default_factory=lambda: RedisDsn("redis://localhost:6379/1"),
    )
    """URL for the redis instance, used by the worker queue."""

    arq_mode: ArqMode = Field(ArqMode.production, alias="NOTEBURST_ARQ_MODE")

    @property
    def arq_redis_settings(self) -> RedisSettings:
        """Create a Redis settings instance for arq."""
        # url_parts = urlparse(self.redis_url)
        redis_settings = RedisSettings(
            host=self.redis_url.host or "localhost",
            port=self.redis_url.port or 6379,
            database=int(self.redis_url.path.lstrip("/"))
            if self.redis_url.path
            else 0,
        )
        return redis_settings


class WorkerConfig(Config):
    identities_path: Path = Field(
        ..., alias="NOTEBURST_WORKER_IDENTITIES_PATH"
    )
    """Path to the configuration file with the pool of Science Platform
    identities available to workers.
    """

    queue_name: str = Field("arq:queue", alias="NOTEBURST_WORKER_QUEUE_NAME")
    """Name of the arq queue that the worker processes from."""

    identity_lock_redis_url: RedisDsn = Field(
        alias="NOTEBURST_WORKER_LOCK_REDIS_URL",
        # Preferred by mypy over a string default
        default_factory=lambda: RedisDsn("redis://localhost:6379/1"),
    )

    job_timeout: int = Field(
        300,
        alias="NOTEBURST_WORKER_JOB_TIMEOUT",
        description=(
            "The timeout, in seconds, for a job until it is timed out."
        ),
    )

    worker_token_lifetime: int = Field(
        2419200,
        alias="NOTEBURST_WORKER_TOKEN_LIFETIME",
        description="Worker auth token lifetime in seconds.",
    )

    worker_token_scopes: str = Field(
        "exec:notebook",
        alias="NOTEBURST_WORKER_TOKEN_SCOPES",
        description=(
            "Worker (nublado2 pod) token scopes as a comma-separated string."
        ),
    )

    image_selector: JupyterImageSelector = Field(
        JupyterImageSelector.recommended,
        alias="NOTEBURST_WORKER_IMAGE_SELECTOR",
        description="Method for selecting a Jupyter image to run.",
    )

    image_reference: Optional[str] = Field(
        None,
        alias="NOTEBURST_WORKER_IMAGE_REFERENCE",
        description=(
            "Docker image reference, if NOTEBURST_WORKER_IMAGE_SELECTOR is "
            "``reference``."
        ),
    )

    worker_keepalive: WorkerKeepAliveSetting = Field(
        WorkerKeepAliveSetting.normal, alias="NOTEBURST_WORKER_KEEPALIVE"
    )

    @property
    def aioredlock_redis_config(self) -> list[str]:
        """Redis configurations for aioredlock."""
        return [str(self.identity_lock_redis_url)]

    @validator("image_reference")
    def is_image_ref_set(
        cls, v: Optional[str], values: Mapping[str, Any]
    ) -> Optional[str]:
        """Validate that image_reference is set if image_selector is
        set to reference.
        """
        if (
            v is None
            and values["image_selector"] == JupyterImageSelector.reference
        ):
            raise ValueError(
                "Set NOTEBURST_WORKER_IMAGE_REFERENCE since "
                "NOTEBURST_WORKER_IMAGE_SELECTOR is ``reference``."
            )

        return v

    @property
    def parsed_worker_token_scopes(self) -> list[str]:
        """Sequence of worker token scopes, parsed from the comma-separated
        list in `worker_token_scopes`.
        """
        return [t.strip() for t in self.worker_token_scopes.split(",") if t]


config = Config()
"""Configuration for noteburst."""
