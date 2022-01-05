"""HTTP API endpoints for prototyping and testing the services."""

from __future__ import annotations

import asyncio

import httpx
import structlog
from fastapi import APIRouter, BackgroundTasks, Depends
from safir.dependencies.http_client import http_client_dependency
from safir.dependencies.logger import logger_dependency

from noteburst.dependencies.arqpool import ArqPool, arq_dependency
from noteburst.jupyterclient.jupyterlab import (
    JupyterClient,
    JupyterConfig,
    JupyterImageSelector,
)
from noteburst.jupyterclient.user import User

from .models import PostCodeRequest, PostLoginRequest

prototype_router = APIRouter(prefix="/prototype")


@prototype_router.post(
    "/login",
    description=(
        "Demonstrate authenticating a user, without spawning a JupyterLab pod."
    ),
    status_code=200,
)
async def post_login(
    request_data: PostLoginRequest,
    http_client: httpx.AsyncClient = Depends(http_client_dependency),
    logger: structlog.BoundLogger = Depends(logger_dependency),
) -> None:
    user = User(username=request_data.username, uid=request_data.uid)
    authed_user = await user.login(
        scopes=["exec:notebook"], http_client=http_client
    )
    logger.info(
        "Authenticated user", user=authed_user.username, uid=authed_user.uid
    )


@prototype_router.post(
    "/spawn",
    description=(
        "Demonstrate authenticating a user and spawning a JupyterLab pod."
    ),
    status_code=202,
)
async def post_spawn(
    background_tasks: BackgroundTasks,
    request_data: PostLoginRequest,
    http_client: httpx.AsyncClient = Depends(http_client_dependency),
    logger: structlog.BoundLogger = Depends(logger_dependency),
) -> None:
    background_tasks.add_task(
        run_spawn_cycle,
        username=request_data.username,
        uid=request_data.uid,
        logger=logger,
        http_client=http_client,
    )


@prototype_router.post(
    "/code",
    description=("Run python code in a JupyterLab kernel."),
    status_code=202,
)
async def post_code(
    background_tasks: BackgroundTasks,
    request_data: PostCodeRequest,
    http_client: httpx.AsyncClient = Depends(http_client_dependency),
    logger: structlog.BoundLogger = Depends(logger_dependency),
) -> None:
    background_tasks.add_task(
        run_code,
        username=request_data.username,
        uid=request_data.uid,
        code=request_data.code,
        logger=logger,
        http_client=http_client,
    )


async def run_spawn_cycle(
    *,
    username: str,
    uid: str,
    logger: structlog.BoundLogger,
    http_client: httpx.AsyncClient,
) -> None:
    user = User(username=username, uid=uid)
    authed_user = await user.login(
        scopes=["exec:notebook"], http_client=http_client
    )
    logger.info(
        "Authenticated user", user=authed_user.username, uid=authed_user.uid
    )

    jupyter_config = JupyterConfig(
        image_selector=JupyterImageSelector.RECOMMENDED
    )

    async with JupyterClient(
        user=authed_user, logger=logger, config=jupyter_config
    ) as jupyter_client:
        await jupyter_client.log_into_hub()
        logger.info("Logged into JupyterHub")

        image_info = await jupyter_client.spawn_lab()
        logger.info("Spawning a JupyterLab", image_info=image_info)
        async for progress in jupyter_client.spawn_progress():
            logger.info("Spawning progress", progress_message=str(progress))

        logger.info("Logging into JupyterLab")
        await jupyter_client.log_into_lab()

        logger.info("Finished logging into JupyterLab")

        asyncio.sleep(30.0)

        logger.info("Stopping JupyterLab")
        await jupyter_client.stop_lab()
        logger.info("Stopped JupyterLab")


async def run_code(
    *,
    username: str,
    uid: str,
    code: str,
    logger: structlog.BoundLogger,
    http_client: httpx.AsyncClient,
) -> None:
    user = User(username=username, uid=uid)
    authed_user = await user.login(
        scopes=["exec:notebook"], http_client=http_client
    )
    logger.info(
        "Authenticated user", user=authed_user.username, uid=authed_user.uid
    )

    jupyter_config = JupyterConfig(
        image_selector=JupyterImageSelector.RECOMMENDED
    )

    async with JupyterClient(
        user=authed_user, logger=logger, config=jupyter_config
    ) as jupyter_client:
        await jupyter_client.log_into_hub()
        logger.info("Logged into JupyterHub")

        if await jupyter_client.is_lab_stopped():
            image_info = await jupyter_client.spawn_lab()
            logger.info("Spawning a JupyterLab", image_info=image_info)
            async for progress in jupyter_client.spawn_progress():
                logger.info(
                    "Spawning progress", progress_message=str(progress)
                )

        logger.info("Logging into JupyterLab")
        await jupyter_client.log_into_lab()

        logger.info("Finished logging into JupyterLab")

        async with jupyter_client.open_lab_session() as lab_session:
            result = await lab_session.run_python(code)
            logger.info("Finished running code", result=result)

        logger.info("Stopping JupyterLab")
        await jupyter_client.stop_lab()
        logger.info("Stopped JupyterLab")


@prototype_router.post(
    "/ping", description="Enqueue the ping worker task.", status_code=202
)
async def post_ping(
    *,
    logger: structlog.BoundLogger = Depends(logger_dependency),
    arq_pool: ArqPool = Depends(arq_dependency),
) -> None:
    logger.info("Enqueing a ping task")
    await arq_pool.enqueue_job("ping")
    logger.info("Finished enqueing a ping task")
