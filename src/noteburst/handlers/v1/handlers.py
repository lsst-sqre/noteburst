"""V1 REST API handlers."""

from fastapi import APIRouter

v1_router = APIRouter(tags=["v1"])
"""FastAPI router for the /v1/ REST API"""


@v1_router.get("/")
async def get_index() -> str:
    return "Hello world"
