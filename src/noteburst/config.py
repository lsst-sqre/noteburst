"""Configuration definition."""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Annotated, Self, assert_never, override

from arq.connections import RedisSettings
from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    RedisDsn,
    SecretStr,
    model_validator,
)
from pydantic.alias_generators import to_camel
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)
from rubin.nublado.client.models import (
    NubladoImage,
    NubladoImageByClass,
    NubladoImageByReference,
    NubladoImageClass,
)
from safir.arq import ArqMode
from safir.logging import LogLevel, Profile
from safir.metrics import MetricsConfiguration, metrics_configuration_factory

from .constants import CONFIG_PATH_ENV_VAR, DEFAULT_CONFIG_PATH

__all__ = [
    "Config",
    "JupyterImageSelector",
    "WorkerConfig",
    "WorkerKeepAliveSetting",
]


class JupyterImageSelector(str, Enum):
    """Possible ways of selecting a JupyterLab image."""

    recommended = "recommended"
    """Currently recommended image."""

    weekly = "weekly"
    """Current weekly image."""

    reference = "reference"
    """Select a specific image by reference."""


class WorkerKeepAliveSetting(str, Enum):
    """Modes for the worker keep-alive function."""

    disabled = "disabled"
    """Do not run a keep-alive function."""

    fast = "fast"
    """Run the keep-alive function at a high frequency (every 30 seconds)."""

    normal = "normal"
    """Run the keep-alive function at a slower frequency (i.e. 5 minutes)."""

    hourly = "hourly"
    """Run the keep-alive function every hour."""

    daily = "daily"
    """Run the keep-alive function at a very slow frequency (i.e. 24 hours)."""


class Identity(BaseModel):
    """Model for a single user identity."""

    username: Annotated[
        str, Field(description="The username of the user account.")
    ]

    uid: Annotated[
        int | None,
        Field(
            description=(
                "The UID of the user account. This can be `None` if the "
                "authentication system assigns the UID."
            )
        ),
    ] = None

    gid: Annotated[
        int | None,
        Field(
            description=(
                "The GID of the user account. This can be `None` if the "
                "authentication system assigns the GID."
            )
        ),
    ] = None


class Config(BaseSettings):
    """Noteburst app configuration."""

    name: str = "Noteburst"

    profile: Profile = Profile.production

    log_level: LogLevel = LogLevel.INFO

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
            description="The URL path prefix where noteburst is hosted.",
        ),
    ] = "/noteburst"

    metrics: Annotated[
        MetricsConfiguration,
        Field(
            default_factory=metrics_configuration_factory,
            title="Metrics configuration",
        ),
    ]

    environment_url: Annotated[
        HttpUrl,
        Field(
            description=(
                "The base URL of the Rubin Science Platform environment. This "
                "is used for creating URLs to services, such as JupyterHub."
            ),
        ),
    ]

    jupyterhub_path_prefix: Annotated[
        str,
        Field(description="The path prefix for the JupyterHub service."),
    ] = "/nb/"

    nublado_controller_path_prefix: Annotated[
        str,
        Field(
            description="The path prefix for the Nublado controller service.",
        ),
    ] = "/nublado"

    gafaelfawr_token: Annotated[
        SecretStr,
        Field(
            description=(
                "This token is used to make an admin API call to Gafaelfawr "
                "to get a token for the user."
            ),
        ),
    ]

    redis_url: Annotated[
        RedisDsn,
        Field(
            # Preferred by mypy over a string default
            default_factory=lambda: RedisDsn("redis://localhost:6379/1"),
            description=(
                "URL for the redis instance, used by the worker queue."
            ),
        ),
    ]

    arq_mode: Annotated[
        ArqMode,
        Field(
            description=(
                "The Arq mode. Use 'test' to mock arq/redis for testing."
            ),
        ),
    ] = ArqMode.production

    slack_webhook_url: Annotated[
        HttpUrl | None,
        Field(
            description=(
                "Webhook URL for sending error messages to a Slack channel."
            ),
        ),
    ] = None

    sentry_traces_sample_rate: Annotated[
        float,
        Field(
            default=0,
            description=(
                "If Sentry is enabled (by providing a SENTRY_DSN env var"
                "value), this is a number between 0 and 1 that is a percentage"
                "of the number of requests that are traced."
            ),
            ge=0,
            le=1,
        ),
    ]

    @property
    def arq_redis_settings(self) -> RedisSettings:
        """Create a Redis settings instance for arq."""
        return RedisSettings(
            host=self.redis_url.host or "localhost",
            port=self.redis_url.port or 6379,
            database=(
                int(self.redis_url.path.lstrip("/"))
                if self.redis_url.path
                else 0
            ),
        )

    @classmethod
    @override
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Add a YAML source to the default settings sources."""
        config_path = Path(
            os.environ.get(CONFIG_PATH_ENV_VAR, DEFAULT_CONFIG_PATH)
        )
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
            YamlConfigSettingsSource(settings_cls, yaml_file=config_path),
        )

    model_config = SettingsConfigDict(
        env_prefix="NOTEBURST_", alias_generator=to_camel
    )


class WorkerConfig(Config):
    """Configuration superset for arq worker processes."""

    identities: Annotated[
        list[Identity],
        Field(
            description=(
                "A list of available RSP identities to execute notebooks with."
            )
        ),
    ]

    identity_index: Annotated[
        int,
        Field(
            description=(
                "The index the identity in the identities list to use."
            )
        ),
    ]

    queue_name: Annotated[
        str,
        Field(
            description=(
                "Name of the arq queue that the worker processes from."
            ),
        ),
    ] = "arq:queue"

    identity_lock_redis_url: Annotated[
        RedisDsn,
        Field(
            # Preferred by mypy over a string default
            default_factory=lambda: RedisDsn("redis://localhost:6379/1"),
            description=(
                "URL for the redis instance, used by the worker to lock "
                "JupyterLab user identities to a worker instance."
            ),
        ),
    ]

    job_timeout: Annotated[
        int,
        Field(
            description=(
                "The timeout, in seconds, for a job until it is timed out."
            ),
        ),
    ] = 300

    max_concurrent_jobs: Annotated[
        int,
        Field(
            description=(
                "The maximum number of concurrent jobs a worker can handle. "
                "This should be equal to less than the number of CPUs on the "
                "JupyterLab pod."
            ),
        ),
    ] = 3

    worker_token_lifetime: Annotated[
        int,
        Field(
            description="Worker auth token lifetime in seconds.",
        ),
    ] = 2419200

    worker_token_scopes: Annotated[
        str,
        Field(
            description=(
                "Worker (nublado pod) token scopes as a comma-separated "
                "string."
            ),
        ),
    ] = "exec:notebook"

    image_selector: Annotated[
        JupyterImageSelector,
        Field(
            description="Method for selecting a Jupyter image to run.",
        ),
    ] = JupyterImageSelector.recommended

    image_reference: Annotated[
        str | None,
        Field(
            description=(
                "Docker image reference, if NOTEBURST_WORKER_IMAGE_SELECTOR "
                "is ``reference``."
            ),
        ),
    ] = None

    worker_keepalive: Annotated[
        WorkerKeepAliveSetting,
        Field(
            description=(
                "Keep-alive setting for the worker process. This setting "
                "must be fast enough to defeat the Nublado pod culler."
            ),
        ),
    ] = WorkerKeepAliveSetting.normal

    @property
    def aioredlock_redis_config(self) -> list[str]:
        """Redis configurations for aioredlock."""
        return [str(self.identity_lock_redis_url)]

    @model_validator(mode="after")
    def is_image_ref_set(self) -> Self:
        """Validate that image_reference is set if image_selector is
        set to reference.
        """
        if (
            self.image_reference is None
            and self.image_selector == JupyterImageSelector.reference
        ):
            raise ValueError(
                "Set NOTEBURST_WORKER_IMAGE_REFERENCE since "
                "NOTEBURST_WORKER_IMAGE_SELECTOR is ``reference``."
            )

        return self

    @property
    def parsed_worker_token_scopes(self) -> list[str]:
        """Sequence of worker token scopes, parsed from the comma-separated
        list in `worker_token_scopes`.
        """
        return [t.strip() for t in self.worker_token_scopes.split(",") if t]

    @property
    def nublado_image(self) -> NubladoImage:
        """The JupyterLab image to use for the pod."""
        match self.image_selector:
            case JupyterImageSelector.recommended:
                return NubladoImageByClass(
                    image_class=NubladoImageClass.RECOMMENDED
                )
            case JupyterImageSelector.weekly:
                return NubladoImageByClass(
                    image_class=NubladoImageClass.LATEST_WEEKLY
                )
            case JupyterImageSelector.reference:
                return NubladoImageByReference(reference=self.image_reference)
            case _:
                assert_never(self.image_selector)

    @property
    def identity(self) -> Identity:
        """The RSP identity that this worker should use."""
        try:
            return self.identities[self.identity_index]
        except IndexError as err:
            raise ValueError(
                f"No identity configured for index: {self.identity_index}. "
                f"Identities: {list(enumerate(self.identities))}"
            ) from err


config = Config()
"""Configuration for noteburst."""
