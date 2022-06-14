"""Configuration definition."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, List, Mapping, Optional
from urllib.parse import urlparse

from arq.connections import RedisSettings
from pydantic import (
    BaseSettings,
    Field,
    HttpUrl,
    RedisDsn,
    SecretStr,
    validator,
)
from safir.arq import ArqMode

__all__ = ["Config", "Profile", "LogLevel"]


class Profile(str, Enum):

    production = "production"

    development = "development"


class LogLevel(str, Enum):

    DEBUG = "DEBUG"

    INFO = "INFO"

    WARNING = "WARNING"

    ERROR = "ERROR"

    CRITICAL = "CRITICAL"


class JupyterImageSelector(str, Enum):
    """Possible ways of selecting a JupyterLab image."""

    recommended = "recommended"
    """Currently recommended image."""

    weekly = "weekly"
    """Current weekly image."""

    reference = "reference"
    """Select a specific image by reference."""


class Config(BaseSettings):

    name: str = Field("Noteburst", env="SAFIR_NAME")

    profile: Profile = Field(Profile.production, env="SAFIR_PROFILE")

    log_level: LogLevel = Field(LogLevel.INFO, env="SAFIR_LOG_LEVEL")

    logger_name: str = "noteburst"
    """The root name of the Python logger, which is also the name of the
    root Python module.
    """

    path_prefix: str = Field("/noteburst", env="NOTEBURST_PATH_PREFIX")
    """The URL path prefix where noteburst is hosted."""

    environment_url: HttpUrl = Field(env="NOTEBURST_ENVIRONMENT_URL")
    """The base URL of the Rubin Science Platform environment.

    This is used for creating URLs to services, such as JupyterHub.
    """

    gafaelfawr_token: SecretStr = Field(env="NOTEBURST_GAFAELFAWR_TOKEN")
    """This token is used to make an admin API call to Gafaelfawr to get a
    token for the user.
    """

    redis_url: RedisDsn = Field(
        "redis://localhost:6379/0", env="NOTEBURST_REDIS_URL"
    )
    """URL for the redis instance, used by the worker queue."""

    arq_mode: ArqMode = Field(ArqMode.production, env="NOTEBURST_ARQ_MODE")

    @property
    def arq_redis_settings(self) -> RedisSettings:
        """Create a Redis settings instance for arq."""
        url_parts = urlparse(self.redis_url)
        redis_settings = RedisSettings(
            host=url_parts.hostname or "localhost",
            port=url_parts.port or 6379,
            database=int(url_parts.path.lstrip("/")) if url_parts.path else 0,
        )
        return redis_settings


class WorkerConfig(Config):

    identities_path: Path = Field(..., env="NOTEBURST_WORKER_IDENTITIES_PATH")
    """Path to the configuration file with the pool of Science Platform
    identities available to workers.
    """

    queue_name: str = Field("arq:queue", env="NOTEBURST_WORKER_QUEUE_NAME")
    """Name of the arq queue that the worker processes from."""

    identity_lock_redis_url: RedisDsn = Field(
        "redis://localhost:6379/1", env="NOTEBURST_WORKER_LOCK_REDIS_URL"
    )

    job_timeout: int = Field(
        300,
        env="NOTEBURST_WORKER_JOB_TIMEOUT",
        description=(
            "The timeout, in seconds, for a job until it is timed out."
        ),
    )

    worker_token_lifetime: int = Field(
        2419200,
        env="NOTEBURST_WORKER_TOKEN_LIFETIME",
        description="Worker auth token lifetime in seconds.",
    )

    image_selector: JupyterImageSelector = Field(
        JupyterImageSelector.recommended,
        env="NOTEBURST_WORKER_IMAGE_SELECTOR",
        description="Method for selecting a Jupyter image to run.",
    )

    image_reference: Optional[str] = Field(
        None,
        env="NOTEBURST_WORKER_IMAGE_REFERENCE",
        description=(
            "Docker image reference, if NOTEBURST_WORKER_IMAGE_SELECTOR is "
            "``reference``."
        ),
    )

    @property
    def aioredlock_redis_config(self) -> List[str]:
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


config = Config()
"""Configuration for noteburst."""
