"""Configuration definition."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import List
from urllib.parse import urlparse

from arq.connections import RedisSettings
from pydantic import BaseSettings, Field, HttpUrl, RedisDsn, SecretStr

from noteburst.dependencies.arqpool import ArqMode

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


class Config(BaseSettings):

    name: str = Field("noteburst", env="SAFIR_NAME")

    profile: Profile = Field(Profile.production, env="SAFIR_PROFILE")

    log_level: LogLevel = Field(LogLevel.INFO, env="SAFIR_LOG_LEVEL")

    logger_name: str = Field("noteburst", env="SAFIR_LOGGER")

    environment_url: HttpUrl = Field(env="NOTEBURST_ENVIRONMENT_URL")
    """The base URL of the Rubin Science Platform environment.

    This is used for creating URLs to services, such as JupyterHub.
    """

    gafaelfawr_token: SecretStr = Field(env="NOTEBURST_GAFAELFAWR_TOKEN")
    """This token is used to make an admin API call to Gafaelfawr to get a
    token for the user.
    """

    redis_url: RedisDsn = Field(
        "redis://localhost:6379", env="NOTEBURST_REDIS_URL"
    )
    """URL for the redis instance, used by the worker queue."""

    arq_mode: ArqMode = Field(ArqMode.production, env="NOTEBURST_ARQ_MODE")

    @property
    def arq_redis_settings(self) -> RedisSettings:
        """Create a Redis settings instance for arq."""
        url_parts = urlparse(self.redis_url)
        redis_settings = RedisSettings(
            host=url_parts.hostname if url_parts.hostname else "localhost",
            port=url_parts.port if url_parts.port else 6379,
        )
        return redis_settings


class WorkerConfig(Config):

    identities_path: Path = Field(..., env="NOTEBURST_WORKER_IDENTITIES_PATH")
    """Path to the configuration file with the pool of Science Platform
    identities available to workers.
    """

    queue_name: str = Field("arq:queue", env="NOTEBURST_WORKER_QUEUE_NAME")
    """Name of the arq queue that the worker processes from."""

    @property
    def aioredlock_redis_config(self) -> List[str]:
        """Redis configurations for aioredlock."""
        return [str(self.redis_url)]


config = Config()
"""Configuration for noteburst."""
