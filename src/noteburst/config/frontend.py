"""Config for the Noteburst frontend."""

from typing import Annotated

from pydantic import Field, HttpUrl, SecretStr
from safir.arq import ArqMode
from safir.logging import LogLevel, Profile

from .base import BaseConfig

__all__ = ["FrontendConfig"]


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

    jupyterhub_path_prefix: Annotated[
        str,
        Field(
            alias="NOTEBURST_JUPYTERHUB_PATH_PREFIX",
            description="The path prefix for the JupyterHub service.",
        ),
    ] = "/nb/"

    nublado_controller_path_prefix: Annotated[
        str,
        Field(
            alias="NOTEBURST_NUBLADO_CONTROLLER_PATH_PREFIX",
            description="The path prefix for the Nublado controller service.",
        ),
    ] = "/nublado"

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


config = FrontendConfig()
"""Configuration for the Noteburst frontend."""
