"""The main application factory for the noteburst service.

Notes
-----
Be aware that, following the normal pattern for FastAPI services, the app is
constructed when this module is loaded and is not deferred until a function is
called.
"""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version
from pathlib import Path

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from safir.dependencies.arq import arq_dependency
from safir.dependencies.http_client import http_client_dependency
from safir.fastapi import ClientRequestError, client_request_error_handler
from safir.logging import configure_logging, configure_uvicorn_logging
from safir.middleware.x_forwarded import XForwardedMiddleware

from .config import config
from .handlers.external import external_router
from .handlers.internal import internal_router
from .handlers.v1 import v1_router

__all__ = ["app", "config"]


configure_logging(
    profile=config.profile,
    log_level=config.log_level,
    name=config.logger_name,
)
configure_uvicorn_logging(config.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Start up event
    await arq_dependency.initialize(
        mode=config.arq_mode, redis_settings=config.arq_redis_settings
    )

    yield

    # Shut down event
    await http_client_dependency.aclose()


app = FastAPI(
    title=config.name,
    description=Path(__file__).parent.joinpath("description.md").read_text(),
    version=version("noteburst"),
    openapi_url=f"{config.path_prefix}/openapi.json",
    docs_url=f"{config.path_prefix}/docs",
    redoc_url=f"{config.path_prefix}/redoc",
    openapi_tags=[{"name": "v1", "description": "Noteburst v1 REST API"}],
    lifespan=lifespan,
)
"""The FastAPI application for noteburst."""

# Attach routers. Externally-accessible endpoints always use the app's
# configured name as a path prefix, matching the ingress configuration.
app.include_router(internal_router)
app.include_router(external_router, prefix=f"{config.path_prefix}")
app.include_router(v1_router, prefix=f"{config.path_prefix}/v1")

# Add middleware
app.add_middleware(XForwardedMiddleware)

app.exception_handler(ClientRequestError)(client_request_error_handler)


def create_openapi() -> str:
    """Create the OpenAPI spec for static documentation."""
    spec = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    return json.dumps(spec)
