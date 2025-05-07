"""Events helpers that can be lifted into Safir."""

from collections.abc import Awaitable, Callable
from typing import Any, Concatenate

__all__ = ["emit_task_metrics"]


def emit_task_metrics[**P, R](
    f: Callable[Concatenate[dict[str, Any], P], Awaitable[R]],
) -> Callable[Concatenate[dict[str, Any], P], Awaitable[R]]:
    """Emit metrics events for the decorated ARQ task."""

    async def wrapper(
        ctx: dict[Any, Any], *args: P.args, **kwargs: P.kwargs
    ) -> R:
        return await f(ctx, *args, **kwargs)

    return wrapper
