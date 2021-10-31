"""Client for the cachemachine service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Optional
from urllib.parse import urljoin

from noteburst.config import config

if TYPE_CHECKING:
    from typing import List

    import httpx


@dataclass
class JupyterImage:
    """A model for a JupyterImage."""

    reference: str
    """Docker reference to the JupyterLab image to spawn."""

    name: str
    """Label of the image in the spawner page."""

    digest: Optional[str] = None
    """Hash of the last layer of the Docker container.

    May be null if the digest isn't known.
    """

    def __str__(self) -> str:
        return "|".join([self.reference, self.name, self.digest or ""])

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "JupyterImage":
        """Create a JupyterImage from a dict containing ``image_url``,
        ``name``, and ``image_hash`` keys.
        """
        return JupyterImage(
            reference=data["image_url"],
            name=data["name"],
            digest=data["image_hash"],
        )

    @classmethod
    def from_reference(cls, reference: str) -> "JupyterImage":
        return cls(
            reference=reference, name=reference.rsplit(":", 1)[1], digest=""
        )


class CachemachineError(Exception):
    """Unable to get image information from cachemachine."""


class CachemachineClient:
    """Query the cachemachine service for image information.

    Cachemachine is canonical for the available images and details such as
    which image is recommended and what the latest weeklies are.  This client
    queries it and returns the image that matches some selection criteria.
    The resulting string can be passed in to the JupyterHub options form.
    """

    def __init__(self, http_client: httpx.AsyncClient, token: str) -> None:
        self._http_client = http_client
        self._token = token
        self._url = urljoin(
            config.environment_url, "cachemachine/jupyter/available"
        )

    async def get_latest_weekly(self) -> JupyterImage:
        """Image for the latest weekly version.

        Returns
        -------
        image : `JupyterImage`
            The corresponding image.

        Raises
        ------
        CachemachineError
            Some error occurred talking to cachemachine or cachemachine does
            not have any weekly images.
        """
        for image in await self._get_images():
            if image.name.startswith("Weekly"):
                return image
        raise CachemachineError("No weekly versions found")

    async def get_recommended(self) -> JupyterImage:
        """Image string for the latest recommended version.

        Returns
        -------
        image : `mobu.models.jupyter.JupyterImage`
            The corresponding image.

        Raises
        ------
        mobu.exceptions.CachemachineError
            Some error occurred talking to cachemachine.
        """
        images = await self._get_images()
        return images[0]

    async def _get_images(self) -> List[JupyterImage]:
        headers = {"Authorization": f"bearer {self._token}"}
        r = await self._http_client.get(self._url, headers=headers)
        if r.status_code != 200:
            message = (
                "Cannot get image status from cachemachine: "
                f"{r.status_code} {r.reason_phrase}"
            )
            raise CachemachineError(message)
        try:
            data = r.json()
            return [JupyterImage.from_dict(i) for i in data["images"]]
        except Exception as e:
            msg = f"Invalid response from cachemachine: {str(e)}"
            raise CachemachineError(msg)
