"""The main application factory for the noteburst service.

Notes
-----
Be aware that, following the normal pattern for FastAPI services, the app is
constructed when this module is loaded and is not deferred until a function is
called.
"""

from importlib.metadata import metadata
from pathlib import Path

from fastapi import FastAPI
from safir.dependencies.http_client import http_client_dependency
from safir.logging import configure_logging
from safir.middleware.x_forwarded import XForwardedMiddleware

from .config import config
from .dependencies.arqpool import arq_dependency
from .handlers.external import external_router
from .handlers.internal import internal_router
from .handlers.v1 import v1_router

__all__ = ["app", "config"]


configure_logging(
    profile=config.profile,
    log_level=config.log_level,
    name=config.logger_name,
)

app = FastAPI(
    title=config.name,
    description=Path(__file__).parent.joinpath("description.md").read_text(),
    version=metadata("noteburst").get("Version", "0.0.0"),
    openapi_url=f"{config.path_prefix}/openapi.json",
    docs_url=f"{config.path_prefix}/docs",
    redoc_url=f"{config.path_prefix}/redoc",
)
"""The FastAPI application for noteburst."""

# Attach routers. Externally-accessible endpoints always use the app's
# configured name as a path prefix, matching the ingress configuration.
app.include_router(internal_router)
app.include_router(external_router, prefix=f"{config.path_prefix}")
app.include_router(v1_router, prefix=f"{config.path_prefix}/v1")


@app.on_event("startup")
async def startup_event() -> None:
    app.add_middleware(XForwardedMiddleware)
    await arq_dependency.initialize(
        mode=config.arq_mode, redis_settings=config.arq_redis_settings
    )


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await http_client_dependency.aclose()
