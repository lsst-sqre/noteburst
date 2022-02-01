"""The main application factory for the noteburst service.

Notes
-----
Be aware that, following the normal pattern for FastAPI services, the app is
constructed when this module is loaded and is not deferred until a function is
called.
"""

from importlib.metadata import metadata

from fastapi import FastAPI
from safir.dependencies.http_client import http_client_dependency
from safir.logging import configure_logging
from safir.middleware.x_forwarded import XForwardedMiddleware

from .config import config
from .dependencies.arqpool import arq_dependency
from .handlers.external import external_router
from .handlers.internal import internal_router
from .handlers.prototyping import prototype_router
from .handlers.v1 import v1_router

__all__ = ["app", "config"]


configure_logging(
    profile=config.profile,
    log_level=config.log_level,
    name=config.logger_name,
)

app = FastAPI()
"""The main FastAPI application for noteburst."""

# Define the external routes in a subapp so that it will serve its own OpenAPI
# interface definition and documentation URLs under the external URL.
external_app = FastAPI(
    title="noteburst",
    description=metadata("noteburst").get("Summary", ""),
    version=metadata("noteburst").get("Version", "0.0.0"),
)
external_app.include_router(external_router)
external_app.include_router(v1_router, prefix="/v1")
external_app.include_router(prototype_router)

# Attach the internal routes and subapp to the main application.
app.include_router(internal_router)
app.mount(f"/{config.name}", external_app)


@app.on_event("startup")
async def startup_event() -> None:
    app.add_middleware(XForwardedMiddleware)
    await arq_dependency.initialize(
        mode=config.arq_mode, redis_settings=config.arq_redis_settings
    )


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await http_client_dependency.aclose()
