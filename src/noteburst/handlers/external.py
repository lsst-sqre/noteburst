"""Handlers for the app's external root, ``/noteburst/``."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from safir.dependencies.gafaelfawr import auth_logger_dependency
from safir.metadata import Metadata as SafirMetadata
from safir.metadata import get_metadata
from structlog.stdlib import BoundLogger

from noteburst.config import config

__all__ = ["get_index", "external_router"]

external_router = APIRouter()
"""FastAPI router for all external handlers."""


class Index(BaseModel):
    """Metadata about the application."""

    metadata: Annotated[SafirMetadata, Field(title="Package metadata")]


@external_router.get(
    "/",
    description=("Discover metadata about the application."),
    response_model=Index,
    response_model_exclude_none=True,
    summary="Application metadata",
)
async def get_index(
    logger: Annotated[BoundLogger, Depends(auth_logger_dependency)],
) -> Index:
    """GET ``/noteburst/`` (the app's external root).

    Customize this handler to return whatever the top-level resource of your
    application should return. For example, consider listing key API URLs.
    When doing so, also change or customize the response model in
    `noteburst.models.Index`.

    By convention, the root of the external API includes a field called
    ``metadata`` that provides the same Safir-generated metadata as the
    internal root endpoint.
    """
    # There is no need to log simple requests since uvicorn will do this
    # automatically, but this is included as an example of how to use the
    # logger for more complex logging.
    logger.info("Request for application metadata")

    metadata = get_metadata(
        package_name="noteburst",
        application_name=config.name,
    )
    return Index(metadata=metadata)
