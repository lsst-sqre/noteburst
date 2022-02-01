"""Test fixtures for noteburst tests."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict

import pytest
import respx
import structlog
import websockets
from asgi_lifespan import LifespanManager
from httpx import AsyncClient

from noteburst import main
from tests.support.arq import MockIdentityClaim, MockIdentityManager
from tests.support.cachemachine import mock_cachemachine
from tests.support.jupyter import mock_jupyter, mock_jupyter_websocket

if TYPE_CHECKING:
    from typing import AsyncIterator

    from _pytest.monkeypatch import MonkeyPatch
    from fastapi import FastAPI

    from tests.support.cachemachine import MockCachemachine
    from tests.support.jupyter import MockJupyter, MockJupyterWebSocket


@pytest.fixture
async def app() -> AsyncIterator[FastAPI]:
    """Return a configured test application.

    Wraps the application in a lifespan manager so that startup and shutdown
    events are sent during test execution.
    """
    async with LifespanManager(main.app):
        yield main.app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Return an ``httpx.AsyncClient`` configured to talk to the test app."""
    async with AsyncClient(app=app, base_url="https://example.com/") as client:
        yield client


@pytest.fixture
async def cachemachine(respx_mock: respx.Router) -> MockCachemachine:
    """Mock the cachemachine API."""
    return mock_cachemachine(respx_mock)


@pytest.fixture
def jupyter(monkeypatch: MonkeyPatch, respx_mock: respx.Router) -> MockJupyter:
    """Mock out JupyterHub/Lab API."""
    jupyter_mock = mock_jupyter(respx_mock)

    @contextlib.asynccontextmanager
    async def mock_websocket_connect(
        url: str, **kwargs: Any
    ) -> AsyncGenerator[MockJupyterWebSocket, None]:
        yield mock_jupyter_websocket(url, jupyter_mock)

    monkeypatch.setattr(websockets, "connect", mock_websocket_connect)

    return jupyter_mock


@pytest.fixture
async def worker_context() -> Dict[Any, Any]:
    """A mock ctx (context) fixture for Pytest workers."""
    ctx: Dict[Any, Any] = {}

    # Prep identity_manager
    ctx["identity_manager"] = MockIdentityManager()
    mock_identity = MockIdentityClaim(username="test", uuid="007", valid=True)
    ctx["identity_manager"].set_identity_test(mock_identity)

    # Prep logger
    logger = structlog.get_logger("noteburst")
    logger = logger.bind(username=mock_identity.username)
    ctx["logger"] = logger

    return ctx
