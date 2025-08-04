"""Config for the Noteburst periodic metrics cron."""

from typing import Annotated

from pydantic import Field

from .base import BaseConfig

__all__ = ["PeriodicMetricsConfig"]


class PeriodicMetricsConfig(BaseConfig):
    """Config for the Noteburst periodic metrics cron."""

    queue_names: Annotated[
        list[str],
        Field(
            alias="NOTEBURST_METRICS_QUEUE_NAMES",
            description=(
                "Names of the arq queues that the worker processes from."
            ),
        ),
    ] = ["arq:queue"]  # noqa: RUF012


config = PeriodicMetricsConfig()
"""Configuration for the Noteburst periodic metrics cronjob."""
