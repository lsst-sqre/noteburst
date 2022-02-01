"""Noteburst worker lifecycle configuration."""

from __future__ import annotations

from typing import Any, Dict

import httpx
import structlog
from safir.logging import configure_logging

from noteburst.config import WorkerConfig
from noteburst.jupyterclient.jupyterlab import (
    JupyterClient,
    JupyterConfig,
    JupyterImageSelector,
)
from noteburst.jupyterclient.user import User

from .functions import ping
from .identity import IdentityManager

config = WorkerConfig()


async def startup(ctx: Dict[Any, Any]) -> None:
    """Runs during working start-up to set up the JupyterLab client and
    populate the worker context.

    Notes
    -----
    The following context dictionary keys are populated:

    - ``identity_manager`` (an `IdentityManager` instance)
    - ``logger`` (a logger instance)
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

    logger = logger.bind(worker_username=identity.username)

    http_client = httpx.AsyncClient()
    ctx["http_client"] = http_client

    user = User(username=identity.username, uid=identity.uid)
    authed_user = await user.login(
        scopes=["exec:notebook"], http_client=http_client
    )
    logger.info("Authenticated the worker's user.")

    jupyter_config = JupyterConfig(
        image_selector=JupyterImageSelector.RECOMMENDED
    )
    jupyter_client = JupyterClient(
        user=authed_user, logger=logger, config=jupyter_config
    )
    await jupyter_client.log_into_hub()
    image_info = await jupyter_client.spawn_lab()
    logger = logger.bind(image_ref=image_info.reference)
    async for progress in jupyter_client.spawn_progress():
        continue
    await jupyter_client.log_into_lab()
    ctx["jupyter_client"] = jupyter_client

    ctx["logger"] = logger

    logger.info("Start up complete")


async def shutdown(ctx: Dict[Any, Any]) -> None:
    """Runs during worker shut-down to release the JupyterLab resources
    and identitiy claim.
    """
    if "logger" in ctx.keys():
        logger = ctx["logger"]
    else:
        logger = structlog.get_logger(__name__)
    logger.info("Running worker shutdown.")

    try:
        await ctx["identity_manager"].close()
    except Exception as e:
        logger.warning("Issue closing the identity manager: %s", str(e))

    try:
        await ctx["http_client"].aclose()
    except Exception as e:
        logger.warning("Issue closing the http_client: %s", str(e))

    try:
        await ctx["jupyter_client"].close()
    except Exception as e:
        logger.warning("Issue closing the Jupyter client: %s", str(e))

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
