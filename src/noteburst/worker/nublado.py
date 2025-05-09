"""Nublado interface."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Self

import httpx
from rubin.nublado.client import NubladoClient
from rubin.nublado.client.exceptions import ExecutionAPIError
from rubin.nublado.client.models import NotebookExecutionResult, NubladoImage
from structlog.stdlib import BoundLogger

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
        base_url: str,
        jupyterhub_path_prefix: str,
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
        nublado_image
            The Nublado image to use for the pod.
        base_url
            The base URL of the RSP.
        jupyterhub_path_prefix
            The path prefix for the JupyterHub service.

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
            base_url=base_url,
            logger=logger,
            hub_route=jupyterhub_path_prefix,
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

    async def execute_notebook(
        self,
        *,
        ipynb: str,
    ) -> NotebookExecutionResult:
        """Execute a notebook in the spawned pod.

        Parameters
        ----------
        ipynb
            The notebook content as a string.

        Returns
        -------
        NotebookExecutionResult
            The response from the Nublado notebook execution API.
        """
        username = self.nublado_client.user.username
        url = self.nublado_client._url_for_lab(  # noqa: SLF001
            f"user/{username}/rubin/execution",
        )
        self.logger.debug("Created notebook execution URL", url=url)

        headers: dict[str, str] = {}
        if lab_xsrf := self.nublado_client.lab_xsrf:
            headers["X-XSRFToken"] = lab_xsrf

        start_time = datetime.now(tz=UTC)
        try:
            r = await self.nublado_client.http.post(
                url,
                headers=headers,
                content=ipynb,
                # Apply a timeout on the connection, but not on reading the
                # response. This is because the execution can take a long time
                # to complete, and we don't want to timeout the read.
                timeout=httpx.Timeout(5.0, read=None),
            )
            r.raise_for_status()
        except httpx.ReadTimeout as e:
            raise ExecutionAPIError(
                url=url,
                username=username,
                status=500,
                reason="/rubin/execution endpoint timeout",
                method="POST",
                body=str(e),
                started_at=start_time,
            ) from e
        except httpx.HTTPStatusError as e:
            # This often occurs from timeouts, so we want to convert the
            # generic HTTPError to an ExecutionAPIError
            raise ExecutionAPIError(
                url=url,
                username=username,
                status=r.status_code,
                reason="Internal Server Error",
                method="POST",
                body=str(e),
                started_at=start_time,
            ) from e
        if r.status_code != 200:
            raise ExecutionAPIError.from_response(username, r)
        self.logger.debug("Got response from /rubin/execution", text=r.text)

        return NotebookExecutionResult.model_validate_json(r.text)
