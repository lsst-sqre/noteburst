"""Nublado interface."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Self

from rubin.gafaelfawr import GafaelfawrClient
from rubin.nublado.client import (
    NotebookExecutionResult,
    NubladoClient,
    NubladoImage,
)
from structlog.stdlib import BoundLogger

from .identity import IdentityModel
from .user import AuthenticatedUser, User


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
        identity: IdentityModel,
        nublado_image: NubladoImage,
        gafaelfawr_client: GafaelfawrClient,
        user_token_scopes: list[str],
        user_token_lifetime: int,
        authed_user: AuthenticatedUser | None = None,
        logger: BoundLogger,
    ) -> Self:
        """Spawn a Nublado JupyterLab pod.

        Parameters
        ----------
        identity
            The identity of the user to spawn the pod for.
        logger
            The logger with bound context about the spawned pod.
        gafaelfawr_client
            Shared Gafaelfawr client.
        user_token_scopes
            The scopes to use for the user token.
        user_token_lifetime
            The lifetime of the user token (seconds).
        jupyterlab_image
            The JupyterLab image to use for the pod.
        nublado_image
            The Nublado image to use for the pod.
        authed_user
            If given, an already-authenticated user. Used by the test suite.

        Returns
        -------
        NubladoPod
            The spawned Nublado pod.
        """
        logger = logger.bind(worker_username=identity.username)
        if not authed_user:
            user = User(
                username=identity.username, uid=identity.uid, gid=identity.gid
            )
            authed_user = await user.login(
                scopes=user_token_scopes,
                token_lifetime=user_token_lifetime,
                gafaelfawr_client=gafaelfawr_client,
            )
            logger.info("Authenticated the worker's user.")

        nublado_client = NubladoClient(
            username=authed_user.username,
            token=authed_user.token,
            logger=logger,
        )

        await nublado_client.auth_to_hub()
        logger.info("Authenticated to hub.")

        # If we previously shut down uncleanly, our lab may still be running
        await nublado_client.stop_lab()

        # If we did need to stop a running lab, it will take some time for it
        # to actually stop. Try spawing a few times for this case and other
        # maybe transient error cases.
        logger.info("Starting lab spawn...")
        tries = 5
        while True:
            try:
                await nublado_client.spawn_lab(config=nublado_image)
                await nublado_client.wait_for_spawn()
                break
            except Exception:
                if tries > 0:
                    tries -= 1
                    msg = f"Error spawning lab, trying {tries} more times."
                    logger.exception(msg)
                    await asyncio.sleep(5)
                    continue
                raise

        logger.info("Lab spawned.")
        await nublado_client.auth_to_lab()
        logger.info("Authenticated to lab.")

        return cls(nublado_client=nublado_client, logger=logger)

    async def execute_notebook(
        self, *, ipynb: str, kernel_name: str | None = None
    ) -> NotebookExecutionResult:
        """Execute a notebook in the spawned pod.

        Parameters
        ----------
        ipynb
            The notebook content as a string.
        kernel_name
            The kernel name to use for the notebook execution. If `None`,
            the default kernel is used.

        Returns
        -------
        NotebookExecutionResult
            The response from the Nublado notebook execution API.
        """
        await self.nublado_client.auth_to_lab()
        return await self.nublado_client.run_notebook(
            ipynb, kernel_name=kernel_name
        )
