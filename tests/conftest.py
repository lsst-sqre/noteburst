"""Test fixtures for noteburst tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import respx
from asgi_lifespan import LifespanManager
from httpx import AsyncClient

from noteburst import main
from tests.support.cachemachine import mock_cachemachine
from tests.support.jupyter import mock_jupyter

if TYPE_CHECKING:
    from typing import AsyncIterator

    from fastapi import FastAPI

    from tests.support.cachemachine import MockCachemachine
    from tests.support.jupyter import MockJupyter


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
def jupyter(respx_mock: respx.Router) -> MockJupyter:
    """Mock out JupyterHub/Lab API."""
    return mock_jupyter(respx_mock)
