"""Noteburst worker lifecycle configuration."""

from __future__ import annotations

from typing import Any, Dict

import structlog
from safir.logging import configure_logging

from noteburst.config import WorkerConfig

from .functions import ping

config = WorkerConfig()


async def startup(ctx: Dict[Any, Any]) -> None:
    configure_logging(
        profile=config.profile,
        log_level=config.log_level,
        name="noteburst",
    )
    logger = structlog.get_logger(__name__)
    logger.info("Starting up worker")


async def shutdown(ctx: Dict[Any, Any]) -> None:
    logger = structlog.get_logger(__name__)
    logger.info("Running worker shutdown.")


class WorkerSettings:
    """Configuration for a Noteburst worker.

    See `arq.worker.Worker` for details on these attributes.
    """

    functions = [ping]

    redis_settings = config.arq_redis_settings

    queue_name = config.queue_name

    on_startup = startup

    on_shutdown = shutdown
