"""Noteburst worker lifecycle configuration."""

from __future__ import annotations

from datetime import UTC, datetime
from importlib.metadata import version
from typing import Any, ClassVar

import httpx
import humanize
import rubin.nublado.client.models as nc_models
import sentry_sdk
import structlog
from arq import cron
from rubin.nublado.client.exceptions import (
    JupyterProtocolError,
    JupyterSpawnError,
    JupyterTimeoutError,
    JupyterWebError,
    JupyterWebSocketError,
)
from safir.logging import configure_logging
from safir.sentry import before_send_handler
from safir.slack.blockkit import SlackMessage, SlackTextField
from safir.slack.webhook import SlackWebhookClient

from noteburst.config import (
    JupyterImageSelector,
    WorkerConfig,
    WorkerKeepAliveSetting,
)
from noteburst.exceptions import NoteburstWorkerError

from .functions import keep_alive, nbexec, ping, run_python
from .identity import IdentityManager
from .nublado import NubladoPod

config = WorkerConfig()

# If SENTRY_DSN is not in the environment, this will do nothing
sentry_sdk.init(
    traces_sample_rate=config.sentry_traces_sample_rate,
    before_send=before_send_handler,
)


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

    jupyter_image: nc_models.NubladoImage | None = None
    if config.image_selector == "reference":
        jupyter_image = nc_models.NubladoImageByReference(
            reference=config.image_reference
        )
    elif config.image_selector == "weekly":
        jupyter_image = nc_models.NubladoImageByClass(
            image_class=nc_models.NubladoImageClass.LATEST_WEEKLY
        )
    else:
        # "Recommended" is default
        jupyter_image = nc_models.NubladoImageByClass()

    # Seed an initially-available bot user identity. The while loop below
    # will acquire new identities if spawning with this one fails.
    identity_manager = IdentityManager.from_config(config)
    ctx["identity_manager"] = identity_manager
    identity = await identity_manager.get_identity()

    # Loop with different identities until we get a successful spawn
    nublado_pod: NubladoPod | None = None
    spawn_exception: Exception | None = None
    while True:
        try:
            nublado_pod = await NubladoPod.spawn(
                identity=identity,
                nublado_image=jupyter_image,
                http_client=http_client,
                user_token_scopes=config.parsed_worker_token_scopes,
                user_token_lifetime=config.worker_token_lifetime,
                logger=logger,
            )
            break
        except (
            JupyterProtocolError,
            # Happens when we have orphaned pods and internal jupyterhub errors
            JupyterWebError,
            JupyterSpawnError,
            JupyterTimeoutError,
            JupyterWebSocketError,
            # From the User login with Gafaelfawr
            httpx.HTTPError,
        ) as e:
            logger.warning("Error spawning pod, will re-try with new identity")
            logger.debug("Details for error spawning pod", detail=str(e))
            spawn_exception = e

        # Acquire a new identity and try again
        identity = await identity_manager.get_next_identity(identity)

    if nublado_pod is None:
        raise NoteburstWorkerError(
            "Failed to start up Noteburst worker. Could not spawn a Nublado "
            "pod with any identity.",
            tags={"spawn_exception_type": type(spawn_exception).__name__},
            contexts={
                "nublado": {
                    "username": identity.username,
                    "user_token_scopes": config.parsed_worker_token_scopes,
                    "image_selector": config.image_selector,
                    "image_reference": config.image_reference,
                    "spawn_exception": str(spawn_exception),
                    "spawn_exception_type": type(spawn_exception).__name__,
                }
            },
        )

    ctx["jupyter_client"] = nublado_pod.nublado_client
    ctx["logger"] = nublado_pod.logger

    # continue using logger with bound context
    logger = ctx["logger"]

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
