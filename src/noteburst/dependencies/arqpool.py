"""A FastAPI dependency that supplies a Redis connection for arq."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from arq import create_pool

if TYPE_CHECKING:
    from arq.connections import ArqRedis, RedisSettings


class ArqPool:
    """A FastAPI dependency that maintains a redis client for enqueing
    tasks to the worker pool.
    """

    def __init__(self) -> None:
        self._pool: Optional[ArqRedis] = None

    async def initialize(self, redis_settings: RedisSettings) -> None:
        self._pool = await create_pool(redis_settings)

    async def __call__(self) -> ArqRedis:
        if self._pool is None:
            raise RuntimeError("ArqPool is not initialied")
        return self._pool


arq_dependency = ArqPool()
"""Singleton instance of ArqPool that serves as a FastAPI dependency."""
