"""Test the JupyterClient."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest
import respx
import structlog

from noteburst.jupyterclient.jupyterlab import (
    JupyterClient,
    JupyterConfig,
    JupyterImageSelector,
)
from noteburst.jupyterclient.user import User
from tests.support.gafaelfawr import mock_gafaelfawr

if TYPE_CHECKING:
    from tests.support.cachemachine import MockCachemachine
    from tests.support.jupyter import MockJupyter


@pytest.mark.asyncio
async def test_jupyterclient(
    respx_mock: respx.Router,
    jupyter: MockJupyter,
    cachemachine: MockCachemachine,
) -> None:
    user = User(username="someuser", uid="1234")
    mock_gafaelfawr(
        respx_mock=respx_mock, username=user.username, uid=user.uid
    )

    logger = structlog.get_logger(__name__)

    jupyter_config = JupyterConfig(
        image_selector=JupyterImageSelector.RECOMMENDED
    )

    async with httpx.AsyncClient() as http_client:
        authed_user = await user.login(
            scopes=["exec:notebook"], http_client=http_client
        )
        async with JupyterClient(
            user=authed_user, logger=logger, config=jupyter_config
        ) as jupyter_client:
            await jupyter_client.log_into_hub()

            image_info = await jupyter_client.spawn_lab()
            print(image_info)
            async for progress in jupyter_client.spawn_progress():
                print(progress)

            await jupyter_client.log_into_lab()

            # FIXME the test code for this isn't full set up yet
            # async with jupyter_client.open_lab_session() as lab_session:
            #     print(lab_session.kernel_id)

            await jupyter_client.stop_lab()
