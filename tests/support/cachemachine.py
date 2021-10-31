"""Mock cachemachine for tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from noteburst.config import config

if TYPE_CHECKING:
    import respx

__all__ = ["MockCachemachine", "mock_cachemachine"]


class MockCachemachine:
    """Mock of cachemachine that implements only the ``/available`` image
    API.
    """

    def __init__(self) -> None:
        self.images = json.loads(
            Path(__file__)
            .parent.joinpath("cachemachine_images.json")
            .read_text()
        )

    def available(self, request: httpx.Request) -> httpx.Response:
        body = {"images": self.images}
        return httpx.Response(200, json=body)


def mock_cachemachine(respx_router: respx.Router) -> MockCachemachine:
    """Set up a mock cachemachine."""
    mock_cachemachine = MockCachemachine()
    url = f"{config.environment_url}/cachemachine/jupyter/available"
    respx_router.get(url).mock(side_effect=mock_cachemachine.available)
    return mock_cachemachine
