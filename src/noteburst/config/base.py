"""Config shared by all Noteburst components."""

from typing import Annotated

from arq.connections import RedisSettings
from pydantic import Field, RedisDsn
from pydantic_settings import BaseSettings
from safir.metrics import MetricsConfiguration, metrics_configuration_factory

__all__ = ["BaseConfig"]


class BaseConfig(BaseSettings):
    """Config shared by all Noteburst components."""

    metrics: Annotated[
        MetricsConfiguration,
        Field(
            default_factory=metrics_configuration_factory,
            title="Metrics configuration",
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
