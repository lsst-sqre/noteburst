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
