"""Mock cachemachine for tests."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urljoin

import httpx
import respx

from noteburst.config import config

__all__ = ["MockLabController", "mock_labcontroller"]


class MockLabController:
    """Mock of the JupyterLab Controller that implements only the
    ``GET /nublado/spawner/v1/images`` image API.
    """

    def __init__(self) -> None:
        self.dataset = json.loads(
            Path(__file__)
            .parent.joinpath("controller_images.json")
            .read_text()
        )

    def images(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=self.dataset)


def mock_labcontroller(respx_router: respx.Router) -> MockLabController:
    """Set up a mock JupterLab Controller."""
    m = MockLabController()
    url = urljoin(str(config.environment_url), "/nublado/spawner/v1/images")
    respx_router.get(url).mock(side_effect=m.images)
    return m
