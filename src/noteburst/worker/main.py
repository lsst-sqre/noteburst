"""Noteburst worker lifecycle configuration."""

from __future__ import annotations

from typing import Any, Dict

import structlog
from safir.logging import configure_logging

from noteburst.config import WorkerConfig

from .functions import ping
from .identity import IdentityManager

config = WorkerConfig()


async def startup(ctx: Dict[Any, Any]) -> None:
    """Runs during working start-up to set up the JupyterLab client and
    populate the worker context.
    """
    configure_logging(
        profile=config.profile,
        log_level=config.log_level,
        name="noteburst",
    )
    logger = structlog.get_logger(__name__)
    logger.info("Starting up worker")

    identity_manager = IdentityManager.from_config(config)
    ctx["identity_manager"] = identity_manager

    identity = await identity_manager.get_identity()
    logger.info("Starting up with identity", username=identity.username)


async def shutdown(ctx: Dict[Any, Any]) -> None:
    """Runs during worker shut-down to release the JupyterLab resources
    and identitiy claim.
    """
    logger = structlog.get_logger(__name__)
    logger.info("Running worker shutdown.")

    if "identity_manager" in ctx.keys():
        await ctx["identity_manager"].close()

    logger.info("Worker shutdown complete.")


class WorkerSettings:
    """Configuration for a Noteburst worker.

    See `arq.worker.Worker` for details on these attributes.
    """

    functions = [ping]

    redis_settings = config.arq_redis_settings

    queue_name = config.queue_name

    on_startup = startup

    on_shutdown = shutdown
