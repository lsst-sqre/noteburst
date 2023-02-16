"""Noteburst worker lifecycle configuration."""

from __future__ import annotations

from typing import Any

import httpx
import structlog
from arq import cron
from safir.logging import configure_logging

from noteburst.config import WorkerConfig, WorkerKeepAliveSetting
from noteburst.jupyterclient.jupyterlab import (
    JupyterClient,
    JupyterConfig,
    JupyterError,
)
from noteburst.jupyterclient.user import User

from .functions import keep_alive, nbexec, ping, run_python
from .identity import IdentityManager

config = WorkerConfig()


async def startup(ctx: dict[Any, Any]) -> None:
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

    http_client = httpx.AsyncClient()
    ctx["http_client"] = http_client

    jupyter_config = JupyterConfig(
        image_selector=config.image_selector,
        image_reference=config.image_reference,
    )

    identity = await identity_manager.get_identity()

    while True:
        logger = logger.bind(worker_username=identity.username)

        user = User(username=identity.username, uid=identity.uid)
        authed_user = await user.login(
            scopes=config.parsed_worker_token_scopes,
            http_client=http_client,
            token_lifetime=config.worker_token_lifetime,
        )
        logger.info("Authenticated the worker's user.")

        jupyter_client = JupyterClient(
            user=authed_user, logger=logger, config=jupyter_config
        )
        await jupyter_client.log_into_hub()
        try:
            image_info = await jupyter_client.spawn_lab()
            logger = logger.bind(image_ref=image_info.references)
            async for progress in jupyter_client.spawn_progress():
                continue
            await jupyter_client.log_into_lab()
            break
        except JupyterError:
            logger.warning("Error spawning pod, will re-try with new identity")
            identity = await identity_manager.get_next_identity(identity)

    ctx["jupyter_client"] = jupyter_client
    ctx["logger"] = logger

    logger.info("Start up complete")


async def shutdown(ctx: dict[Any, Any]) -> None:
    """Runs during worker shut-down to release the JupyterLab resources
    and identity claim.
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


# For info on ignoring the type checking here, see
# https://github.com/samuelcolvin/arq/issues/249
cron_jobs: list[cron] = []  # type: ignore
if config.worker_keepalive == WorkerKeepAliveSetting.fast:
    f = cron(keep_alive, second={0, 30}, unique=False)  # type: ignore
    cron_jobs.append(f)
elif config.worker_keepalive == WorkerKeepAliveSetting.normal:
    f = cron(
        keep_alive,  # type: ignore
        minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
        unique=False,
    )
    cron_jobs.append(f)


class WorkerSettings:
    """Configuration for a Noteburst worker.

    See `arq.worker.Worker` for details on these attributes.
    """

    functions = [ping, nbexec, run_python]

    cron_jobs = cron_jobs

    redis_settings = config.arq_redis_settings

    queue_name = config.queue_name

    on_startup = startup

    on_shutdown = shutdown

    job_timeout = config.job_timeout
