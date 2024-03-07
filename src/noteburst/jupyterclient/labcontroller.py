"""Client for the JupyterLab Controller service."""

from __future__ import annotations

from typing import Annotated
from urllib.parse import urljoin

import httpx
from pydantic import BaseModel, ConfigDict, Field

from noteburst.config import config


class JupyterImage(BaseModel):
    """A model for a JupyterLab image in a `LabControllerImages` resource."""

    reference: Annotated[
        str,
        Field(
            examples=["lighthouse.ceres/library/sketchbook:latest_daily"],
            title="Full Docker registry path for lab image",
            description="cf. https://docs.docker.com/registry/introduction/",
        ),
    ]

    name: Annotated[
        str,
        Field(
            examples=["Latest Daily (Daily 2077_10_23)"],
            title="Human-readable version of image tag",
        ),
    ]

    digest: Annotated[
        str | None,
        Field(
            examples=[
                "sha256:e693782192ecef4f7846ad2b21"
                "b1574682e700747f94c5a256b5731331a2eec2"
            ],
            title="unique digest of image contents",
        ),
    ] = None

    tag: Annotated[str, Field(title="Image tag")]

    size: Annotated[
        int | None,
        Field(
            examples=[8675309],
            title="Size in bytes of image.  None if image size is unknown",
        ),
    ] = None

    prepulled: Annotated[
        bool,
        Field(
            examples=[False],
            title="Whether image is prepulled to all eligible nodes",
        ),
    ] = False


def underscore_to_dash(x: str) -> str:
    """Convert underscores to dashes in a string."""
    return x.replace("_", "-")


class LabControllerImages(BaseModel):
    """A model for the ``GET /nublado/spawner/v1/images`` response."""

    recommended: Annotated[
        JupyterImage | None, Field(title="The recommended image")
    ] = None

    latest_weekly: Annotated[
        JupyterImage | None, Field(title="The latest weekly release image")
    ] = None

    latest_daily: Annotated[
        JupyterImage | None, Field(title="The latest daily release image")
    ] = None

    latest_release: Annotated[
        JupyterImage | None, Field(title="The latest release image")
    ] = None

    all: Annotated[
        list[JupyterImage], Field(default_factory=list, title="All images")
    ]

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=underscore_to_dash,
    )
    """Pydantic model configuration."""

    def get_by_reference(self, reference: str) -> JupyterImage | None:
        """Get the JupyterImage with a corresponding reference.

        Parameters
        ----------
        reference
            The image reference.

        Returns
        -------
        JupyterImage or None
            Returns the JupyterImage if found, None otherwise.
        """
        for image in self.all:
            if reference == image.reference:
                return image

        return None


class LabControllerError(Exception):
    """Unable to get image information from the JupyterLab Controller."""


class LabControllerClient:
    """A client for the JupyterLab Controller service.

    The JupyterLab Controller provides the listing of available DockerImages
    for JupyterLab pods, and provides info about what image is "recommended"
    or is the latest weekly or daily image.

    Parameters
    ----------
    http_client
        The HTTPX async client.
    token
        The Gafaelfawr token.
    url_prefix
        The URL path prefix for Nublado JupyterLab Controller service.
    """

    def __init__(
        self, *, http_client: httpx.AsyncClient, token: str, url_prefix: str
    ) -> None:
        self._http_client = http_client
        self._token = token
        self._url_prefix = url_prefix

    async def get_latest_weekly(self) -> JupyterImage:
        """Image for the latest weekly version.

        Returns
        -------
        JupyterImage
            The corresponding image.

        Raises
        ------
        LabControllerError
            Some error occurred talking to JupyterLab Controller or does
            not have any weekly images.
        """
        images = await self._get_images()
        image = images.latest_weekly
        if image is None:
            raise LabControllerError("No weekly image found.")
        return image

    async def get_recommended(self) -> JupyterImage:
        """Image for the latest recommended version.

        Returns
        -------
        JupyterImage
            The corresponding image.

        Raises
        ------
        LabControllerError
            An error occurred talking to JupyterLab Controller.
        """
        images = await self._get_images()
        image = images.recommended
        if image is None:
            raise LabControllerError("No recommended image found.")
        return image

    async def get_by_reference(self, reference: str) -> JupyterImage:
        """Image with a specific reference.

        Returns
        -------
        JupyterImage
            The corresponding image.

        Raises
        ------
        LabControllerError
            An error occurred talking to JupyterLab Controller.
        """
        images = await self._get_images()
        image = images.get_by_reference(reference)
        if image is None:
            raise LabControllerError(
                f"No image with reference {reference} found."
            )
        return image

    async def _get_images(self) -> LabControllerImages:
        headers = {"Authorization": f"bearer {self._token}"}
        url = urljoin(
            str(config.environment_url),
            f"{self._url_prefix}/spawner/v1/images",
        )

        r = await self._http_client.get(url, headers=headers)
        if r.status_code != 200:
            msg = f"Cannot get image status: {r.status_code} {r.reason_phrase}"
            raise LabControllerError(msg)
        try:
            data = r.json()
            return LabControllerImages.model_validate(data)
        except Exception as e:
            msg = f"Invalid response from JupyterLab Controller: {e!s}"
            raise LabControllerError(msg) from e
