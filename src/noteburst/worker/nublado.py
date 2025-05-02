"""Nublado interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self

import httpx
from rubin.nublado.client import NubladoClient
from rubin.nublado.client.models import NubladoImage
from structlog.stdlib import BoundLogger

from noteburst.config import config

from .identity import IdentityClaim
from .user import User


@dataclass
class NubladoPod:
    """A spawned Nublado JupyterLab pod."""

    nublado_client: NubladoClient
    """The Nublado client for the spawned pod."""

    logger: BoundLogger
    """The logger with bound context about the spawned pod."""

    @classmethod
    async def spawn(
        cls,
        *,
        identity: IdentityClaim,
        nublado_image: NubladoImage,
        http_client: httpx.AsyncClient,
        user_token_scopes: list[str],
        user_token_lifetime: int,
        logger: BoundLogger,
    ) -> Self:
        """Spawn a Nublado JupyterLab pod.

        Parameters
        ----------
        identity
            The identity of the user to spawn the pod for.
        logger
            The logger with bound context about the spawned pod.
        http_client
            The HTTP client.
        user_token_scopes
            The scopes to use for the user token.
        user_token_lifetime
            The lifetime of the user token (seconds).
        jupyterlab_image
            The JupyterLab image to use for the pod.

        Returns
        -------
        NubladoPod
            The spawned Nublado pod.
        """
        logger = logger.bind(worker_username=identity.username)
        user = User(
            username=identity.username, uid=identity.uid, gid=identity.gid
        )
        authed_user = await user.login(
            scopes=user_token_scopes,
            token_lifetime=user_token_lifetime,
            http_client=http_client,
        )
        logger.info("Authenticated the worker's user.")

        nublado_client = NubladoClient(
            user=authed_user.create_nublado_client_user(),
            base_url=str(config.environment_url),
            logger=logger,
            hub_route=config.jupyterhub_path_prefix,
        )

        await nublado_client.auth_to_hub()
        await nublado_client.spawn_lab(config=nublado_image)
        async for _ in nublado_client.watch_spawn_progress():
            continue
        await nublado_client.auth_to_lab()

        return cls(
            nublado_client=nublado_client,
            logger=logger,
        )
