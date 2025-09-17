"""Noteburst worker lifecycle configuration."""

from __future__ import annotations

from datetime import UTC, datetime
from importlib.metadata import version
from typing import Any, ClassVar

import httpx
import humanize
import structlog
from arq import cron
from safir.logging import configure_logging
from safir.metrics.arq import initialize_arq_metrics, make_on_job_start
from safir.sentry import initialize_sentry
from safir.slack.blockkit import SlackMessage, SlackTextField
from safir.slack.webhook import SlackWebhookClient

import noteburst
from noteburst.config.worker import (
    JupyterImageSelector,
    WorkerConfig,
    WorkerKeepAliveSetting,
)
from noteburst.exceptions import NoteburstWorkerStartupError

from .functions import keep_alive, nbexec, ping, run_python
from .identity import get_identity
from .nublado import NubladoPod

initialize_sentry(release=noteburst.__version__)

config = WorkerConfig()


async def startup(ctx: dict[Any, Any]) -> None:
    """Set up worker context on startup.

    Notes
    -----
    The following context dictionary keys are populated:

    - ``identity`` (an `IdentityModel` instance)
    - ``logger`` (a logger instance)
    """
    configure_logging(
        profile=config.profile,
        log_level=config.log_level,
        name="noteburst",
    )
    logger = structlog.get_logger(__name__)
    logger.bind(
        image_selector=str(config.image_selector),
        image_reference=config.image_reference,
        version=version("noteburst"),
    )
    logger.info("Starting up worker")

    http_client = httpx.AsyncClient()
    ctx["http_client"] = http_client

    if config.slack_webhook_url:
        slack_client = SlackWebhookClient(
            str(config.slack_webhook_url),
            "Noteburst worker",
            logger=logger,
        )
        ctx["slack"] = slack_client

    identity = get_identity(config)
    logger = logger.bind(
        worker_username=identity.username,
    )
    ctx["identity"] = identity

    try:
        nublado_pod = await NubladoPod.spawn(
            identity=identity,
            nublado_image=config.nublado_image,
            http_client=http_client,
            user_token_scopes=config.parsed_worker_token_scopes,
            user_token_lifetime=config.worker_token_lifetime,
            base_url=str(config.environment_url),
            jupyterhub_path_prefix=config.jupyterhub_path_prefix,
            logger=logger,
        )
    except Exception as e:
        raise NoteburstWorkerStartupError(
            "Failed to start up Noteburst worker. Could not spawn a "
            "Nublado pod.",
            user=identity.username,
            image_selector=config.image_selector,
            image_reference=config.image_reference,
            user_token_scopes=config.parsed_worker_token_scopes,
        ) from e

    # TODO(jonathansick): We can retire the nublado_client context since
    # NubladoPod has a nublado_client attribute.
    ctx["nublado_client"] = nublado_pod.nublado_client
    ctx["nublado_pod"] = nublado_pod
    ctx["logger"] = nublado_pod.logger

    # continue using logger with bound context
    logger = ctx["logger"]

    event_manager = config.metrics.make_manager()
    await event_manager.initialize()
    await initialize_arq_metrics(event_manager, ctx)
    ctx["event_manager"] = event_manager

    logger.info(
        "Noteburst worker startup complete",
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
                    SlackTextField(
                        heading="Image Ref",
                        text=config.image_reference
                        if config.image_selector
                        == JupyterImageSelector.reference
                        else "N/A",
                    ),
                    # TODO(jonathansick): Show the actual image ref always.
                    # This requires adding functionality to the Nublado client.
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
        await ctx["nublado_client"].stop_lab()
    except Exception as e:
        logger.warning(
            "Issue stopping the JupyterLab pod on worker shutdown",
            detail=str(e),
        )

    try:
        is_shutdown = await ctx["nublado_client"].is_lab_stopped()
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
        await ctx["http_client"].aclose()
    except Exception as e:
        logger.warning(
            "Issue closing the http_client on worker shutdown", detail=str(e)
        )

    try:
        await ctx["nublado_client"].close()
    except Exception as e:
        logger.warning("Issue closing the Jupyter client", detail=str(e))

    try:
        await ctx["event_manager"].aclose()
    except Exception as e:
        logger.warning("Issue closing the event_manager", detail=str(e))

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
elif config.worker_keepalive == WorkerKeepAliveSetting.hourly:
    f = cron(
        keep_alive,
        minute=52,  # avoid the top of the hour
        unique=False,
    )
    cron_jobs.append(f)
elif config.worker_keepalive == WorkerKeepAliveSetting.daily:
    f = cron(
        keep_alive,
        hour=0,
        minute=52,
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

    on_job_start = make_on_job_start(config.queue_name)

    job_timeout = config.job_timeout

    max_jobs = config.max_concurrent_jobs
