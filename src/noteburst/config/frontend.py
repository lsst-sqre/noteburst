"""Config for the Noteburst frontend."""

from datetime import timedelta
from typing import Annotated

from pydantic import Field, HttpUrl, SecretStr
from safir.arq import ArqMode
from safir.logging import LogLevel, Profile

from .base import BaseConfig

__all__ = ["NBEXEC_BACKSTOP_MARGIN", "FrontendConfig"]

NBEXEC_BACKSTOP_MARGIN = 60
"""Seconds by which the nbexec arq backstop must exceed the longest
per-request notebook timeout, so that the request's own timeout always fires
first and can be reported as a ``timeout`` error before arq cancels the job.
"""


class FrontendConfig(BaseConfig):
    """Config for the Noteburst frontend."""

    name: Annotated[str, Field(alias="SAFIR_NAME")] = "Noteburst"

    profile: Annotated[Profile, Field(alias="SAFIR_PROFILE")] = (
        Profile.production
    )

    log_level: Annotated[LogLevel, Field(alias="SAFIR_LOG_LEVEL")] = (
        LogLevel.INFO
    )

    logger_name: Annotated[
        str,
        Field(
            description=(
                "The root name of the Python logger, which is also the name "
                "of the root Python module"
            )
        ),
    ] = "noteburst"

    path_prefix: Annotated[
        str,
        Field(
            "/noteburst",
            alias="NOTEBURST_PATH_PREFIX",
            description="The URL path prefix where noteburst is hosted.",
        ),
    ] = "/noteburst"

    environment_url: Annotated[
        HttpUrl,
        Field(
            alias="NOTEBURST_ENVIRONMENT_URL",
            description=(
                "The base URL of the Rubin Science Platform environment. This "
                "is used for creating URLs to services, such as JupyterHub."
            ),
        ),
    ]

    gafaelfawr_token: Annotated[
        SecretStr,
        Field(
            alias="NOTEBURST_GAFAELFAWR_TOKEN",
            description=(
                "This token is used to make an admin API call to Gafaelfawr "
                "to get a token for the user."
            ),
        ),
    ]

    arq_mode: Annotated[
        ArqMode,
        Field(
            alias="NOTEBURST_ARQ_MODE",
            description=(
                "The Arq mode. Use 'test' to mock arq/redis for testing."
            ),
        ),
    ] = ArqMode.production

    slack_webhook_url: Annotated[
        HttpUrl | None,
        Field(
            alias="NOTEBURST_SLACK_WEBHOOK_URL",
            description=(
                "Webhook URL for sending error messages to a Slack channel."
            ),
        ),
    ] = None

    nbexec_job_timeout: Annotated[
        int,
        Field(
            alias="NOTEBURST_WORKER_NBEXEC_JOB_TIMEOUT",
            gt=NBEXEC_BACKSTOP_MARGIN,
            description=(
                "The absolute timeout, in seconds, that arq applies to "
                "`nbexec` (notebook execution) jobs. The frontend rejects "
                "requests whose per-request notebook `timeout` is not at "
                "least `NBEXEC_BACKSTOP_MARGIN` (60) seconds shorter than "
                "this backstop, so that the notebook's own `asyncio.wait_for` "
                "is what fires. arq's timeout cancels the task and records a "
                "bare `TimeoutError` that carries no diagnostic message, "
                "while the notebook's own timeout is reported as a `timeout` "
                "error. Both the frontend and the worker read this variable, "
                "so it must be set identically for both deployments."
            ),
        ),
    ] = 3660

    @property
    def max_notebook_timeout(self) -> timedelta:
        """The longest notebook execution timeout a request may ask for.

        This is the nbexec arq backstop minus `NBEXEC_BACKSTOP_MARGIN`, so
        that an accepted request's own timeout always fires before arq
        cancels the job.
        """
        return timedelta(
            seconds=self.nbexec_job_timeout - NBEXEC_BACKSTOP_MARGIN
        )


config = FrontendConfig()
"""Configuration for the Noteburst frontend."""
