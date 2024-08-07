"""Noteburst worker lifecycle configuration."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

import httpx
import humanize
import structlog
from arq import cron
from safir.logging import configure_logging
from safir.slack.blockkit import SlackMessage, SlackTextField
from safir.slack.webhook import SlackWebhookClient

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
    """Set up worker context on startup.

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

    if config.slack_webhook_url:
        slack_client = SlackWebhookClient(
            str(config.slack_webhook_url),
            "Noteburst worker",
            logger=logger,
        )
        ctx["slack"] = slack_client

    jupyter_config = JupyterConfig(
        url_prefix=config.jupyterhub_path_prefix,
        image_selector=config.image_selector,
        image_reference=config.image_reference,
    )

    identity = await identity_manager.get_identity()

    while True:
        logger = logger.bind(worker_username=identity.username)

        user = User(
            username=identity.username, uid=identity.uid, gid=identity.gid
        )
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
            logger = logger.bind(image_ref=image_info.reference)
            async for _ in jupyter_client.spawn_progress():
                continue
            await jupyter_client.log_into_lab()
            break
        except JupyterError as e:
            logger.warning("Error spawning pod, will re-try with new identity")
            logger.debug("Details for error spawning pod", detail=str(e))
            identity = await identity_manager.get_next_identity(identity)

    ctx["jupyter_client"] = jupyter_client
    ctx["logger"] = logger

    logger.info(
        "Noteburst worker startup complete.",
        image_selector=config.image_selector,
        image_reference=config.image_reference,
    )

    if "slack" in ctx:
        slack_client = ctx["slack"]

        date_created = datetime.now(tz=UTC)

        def create_message(message: str) -> SlackMessage:
            now = datetime.now(tz=UTC)
            age = now - date_created

            return SlackMessage(
                message=message,
                fields=[
                    SlackTextField(
                        heading="Username",
                        text=identity.username,
                    ),
                    SlackTextField(
                        heading="Image Selector",
                        text=config.image_selector,
                    ),
                    SlackTextField(heading="Image", text=image_info.name),
                    SlackTextField(
                        heading="Age", text=humanize.naturaldelta(age)
                    ),
                ],
            )

        ctx["slack_message_factory"] = create_message

        # Make a start-up message
        await slack_client.post(
            ctx["slack_message_factory"]("Noteburst worker started")
        )


async def shutdown(ctx: dict[Any, Any]) -> None:
    """Clean up the worker context on shutdown."""
    if "logger" in ctx:
        logger = ctx["logger"]
    else:
        logger = structlog.get_logger(__name__)
    logger.info("Running worker shutdown.")

    try:
        await ctx["jupyter_client"].stop_lab()
    except Exception as e:
        logger.warning(
            "Issue stopping the JupyterLab pod on worker shutdown",
            detail=str(e),
        )

    try:
        is_shutdown = await ctx["jupyter_client"].is_lab_stopped()
        logger.info(
            f"JupyterLab pod shutdown on worker shutdown {is_shutdown}",
            is_shutdown=is_shutdown,
        )
    except Exception as e:
        logger.warning(
            "Issue getting details on pod shutdown during worker shutdown",
            detail=str(e),
        )

    try:
        await ctx["identity_manager"].close()
    except Exception as e:
        logger.warning(
            "Issue closing the identity manager on worker shutdown",
            detail=str(e),
        )

    try:
        await ctx["http_client"].aclose()
    except Exception as e:
        logger.warning(
            "Issue closing the http_client on worker shutdown", detail=str(e)
        )

    try:
        await ctx["jupyter_client"].close()
    except Exception as e:
        logger.warning("Issue closing the Jupyter client", detail=str(e))

    logger.info("Worker shutdown complete.")

    if "slack" in ctx and "slack_message_factory" in ctx:
        slack_client = ctx["slack"]
        await slack_client.post(
            ctx["slack_message_factory"](
                "Noteburst worker shut down complete."
            )
        )


# For info on ignoring the type checking here, see
# https://github.com/samuelcolvin/arq/issues/249
cron_jobs: list[cron] = []  # type: ignore [valid-type]
if config.worker_keepalive == WorkerKeepAliveSetting.fast:
    f = cron(keep_alive, second={0, 30}, unique=False)
    cron_jobs.append(f)
elif config.worker_keepalive == WorkerKeepAliveSetting.normal:
    f = cron(
        keep_alive,
        minute={0, 15, 30, 45},
        unique=False,
    )
    cron_jobs.append(f)


class WorkerSettings:
    """Configuration for a Noteburst worker.

    See `arq.worker.Worker` for details on these attributes.
    """

    functions: ClassVar = [ping, nbexec, run_python]

    cron_jobs = cron_jobs

    redis_settings = config.arq_redis_settings

    queue_name = config.queue_name

    on_startup = startup

    on_shutdown = shutdown

    job_timeout = config.job_timeout

    max_jobs = config.max_concurrent_jobs
