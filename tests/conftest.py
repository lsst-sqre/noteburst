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
from rubin.nublado.client import MockJupyter, register_mock_jupyter
from rubin.repertoire import Discovery, register_mock_discovery

from noteburst import main
from noteburst.worker.identity import IdentityModel

BASE_URL = "https://example.com"


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
async def mock_jupyter(
    respx_mock: respx.Router,
) -> AsyncGenerator[MockJupyter]:
    async with register_mock_jupyter(respx_mock) as mock:
        yield mock


def mock_discovery(
    respx_mock: respx.Router, monkeypatch: pytest.MonkeyPatch
) -> Discovery:
    monkeypatch.setenv("REPERTOIRE_BASE_URL", "https://example.com/repertoire")
    path = Path(__file__).parent / "data" / "discovery.json"
    return register_mock_discovery(respx_mock, path)


@pytest.fixture
def worker_context() -> dict[Any, Any]:
    """Mock the ctx (context) for arq workers."""
    ctx: dict[Any, Any] = {}

    identity = IdentityModel(username="test", uuid="007", valid=True)
    ctx["identity"] = identity

    # Prep logger
    logger = structlog.get_logger("noteburst")
    logger = logger.bind(username=identity.username)
    ctx["logger"] = logger

    return ctx
