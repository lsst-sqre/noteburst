"""Test fixtures for noteburst tests."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncGenerator, AsyncIterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import pytest_asyncio
import respx
import structlog
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from rubin.nublado.client.testing import (
    MockJupyter,
    MockJupyterWebSocket,
    mock_jupyter,
    mock_jupyter_websocket,
)

from noteburst import main
from tests.support.arq import MockIdentityClaim, MockIdentityManager
from tests.support.labcontroller import MockLabController, mock_labcontroller

BASE_URL = "https://example.com"


@pytest_asyncio.fixture
async def app() -> AsyncIterator[FastAPI]:
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
def labcontroller(respx_mock: respx.Router) -> MockLabController:
    """Mock the JupyterLab Controller API."""
    return mock_labcontroller(respx_mock)


@pytest.fixture
async def jupyter(
    respx_mock: respx.Router, tmp_path: Path
) -> AsyncIterator[MockJupyter]:
    """Mock out JupyterHub/Lab API."""
    jupyter_mock = mock_jupyter(
        respx_mock, base_url=BASE_URL, user_dir=tmp_path
    )

    @contextlib.asynccontextmanager
    async def mock_connect(
        url: str,
        extra_headers: dict[str, str],
        max_size: int | None,
        open_timeout: int,
    ) -> AsyncGenerator[MockJupyterWebSocket]:
        yield mock_jupyter_websocket(url, extra_headers, jupyter_mock)

    with patch("rubin.nublado.client.nubladoclient.websocket_connect") as mock:
        mock.side_effect = mock_connect
        yield jupyter_mock


@pytest.fixture
def worker_context() -> dict[Any, Any]:
    """Mock the ctx (context) for arq workers."""
    ctx: dict[Any, Any] = {}

    # Prep identity_manager
    ctx["identity_manager"] = MockIdentityManager()
    mock_identity = MockIdentityClaim(username="test", uuid="007", valid=True)
    ctx["identity_manager"].set_identity_test(mock_identity)

    # Prep logger
    logger = structlog.get_logger("noteburst")
    logger = logger.bind(username=mock_identity.username)
    ctx["logger"] = logger

    return ctx
