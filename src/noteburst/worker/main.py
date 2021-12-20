"""Noteburst worker lifecycle configuration."""

from __future__ import annotations

from typing import Any, Dict

from noteburst.config import config

from .functions import ping


async def startup(ctx: Dict[Any, Any]) -> None:
    print("Running worker startup")


async def shutdown(ctx: Dict[Any, Any]) -> None:
    print("Running worker shutdown.")


class WorkerSettings:
    """Configuration for a Noteburst worker.

    See `arq.worker.Worker` for details on these attributes.
    """

    functions = [ping]

    redis_settings = config.arq_redis_settings

    on_startup = startup

    on_shutdown = shutdown
