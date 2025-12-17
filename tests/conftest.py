"""Test fixtures for noteburst tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
import respx
import structlog
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from rubin.gafaelfawr import (
    GafaelfawrClient,
    MockGafaelfawr,
    register_mock_gafaelfawr,
)
from rubin.nublado.client import MockJupyter, register_mock_jupyter
from rubin.repertoire import Discovery, register_mock_discovery

from noteburst import main
from noteburst.config.frontend import config
from noteburst.config.worker import WorkerConfig
from noteburst.worker.identity import IdentityModel
from noteburst.worker.nublado import NubladoPod

BASE_URL = "https://example.com"


@pytest.fixture(autouse=True)
def gafaelfawr_token(
    mock_gafaelfawr: MockGafaelfawr, monkeypatch: pytest.MonkeyPatch
) -> str:
    """Replace the Gafaelfawr token with a real one."""
    token = mock_gafaelfawr.create_token(
        "bot-noteburst", scopes=["admin:token", "admin:userinfo"]
    )
    monkeypatch.setattr(config, "gafaelfawr_token", SecretStr(token))
    return token


@pytest_asyncio.fixture
async def app(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[FastAPI]:
    """Return a configured test application.

    Wraps the application in a lifespan manager so that startup and shutdown
    events are sent during test execution.
    """
    async with LifespanManager(main.app):
        yield main.app


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Return an ``httpx.AsyncClient`` configured to talk to the test app."""
    headers = {"X-Auth-Request-User": "user"}
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url=BASE_URL,
        headers=headers,
    ) as client:
        yield client


@pytest.fixture
def mock_discovery(
    respx_mock: respx.Router, monkeypatch: pytest.MonkeyPatch
) -> Discovery:
    monkeypatch.setenv("REPERTOIRE_BASE_URL", "https://example.com/repertoire")
    path = Path(__file__).parent / "data" / "discovery.json"
    return register_mock_discovery(respx_mock, path)


@pytest_asyncio.fixture
async def mock_gafaelfawr(
    respx_mock: respx.Router, mock_discovery: Discovery
) -> MockGafaelfawr:
    return await register_mock_gafaelfawr(respx_mock)


@pytest_asyncio.fixture
async def mock_jupyter(
    respx_mock: respx.Router, mock_discovery: Discovery
) -> AsyncGenerator[MockJupyter]:
    async with register_mock_jupyter(respx_mock) as mock:
        yield mock


@pytest.fixture
def sample_ipynb() -> str:
    path = Path(__file__).parent.joinpath("data/test.ipynb")
    return path.read_text()


@pytest.fixture
def sample_ipynb_executed() -> str:
    path = Path(__file__).parent.joinpath("data/test.nbexec.ipynb")
    return path.read_text()


@pytest_asyncio.fixture
async def worker_context(
    mock_gafaelfawr: MockGafaelfawr, mock_jupyter: MockJupyter
) -> dict[Any, Any]:
    """Mock the ctx (context) for arq workers."""
    ctx: dict[Any, Any] = {}

    identity = IdentityModel(username="bot-test", uid=7777)
    ctx["identity"] = identity

    # Prep logger
    logger = structlog.get_logger("noteburst")
    logger = logger.bind(username=identity.username)
    ctx["logger"] = logger

    # Create a Nublado client.
    config = WorkerConfig()
    nublado_pod = await NubladoPod.spawn(
        identity=identity,
        nublado_image=config.nublado_image,
        gafaelfawr_client=GafaelfawrClient(),
        user_token_scopes=config.parsed_worker_token_scopes,
        user_token_lifetime=config.worker_token_lifetime,
        logger=logger,
    )
    ctx["nublado_client"] = nublado_pod.nublado_client
    ctx["nublado_pod"] = nublado_pod

    return ctx
