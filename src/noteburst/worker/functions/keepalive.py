"""Execute Python in the JupyterLab kernel to prevent it from being culled."""

from __future__ import annotations

import asyncio
import sys
from datetime import timedelta
from typing import Any

from arq.typing import WorkerCoroutine
from rubin.nublado.client.exceptions import (
    JupyterWebError,
    JupyterWebSocketError,
)


async def _keep_alive(
    ctx: dict[Any, Any], retries: int, idle: timedelta
) -> str:
    """Execute Python code in a JupyterLab pod with a specific Jupyter kernel.

    Exit the worker process if this is unsuccessfull after some attempts.

    Parameters
    ----------
    ctx
        Arq worker context.
    retries
        The number of times to retry running the code.
    idle
        The amount of time to wait in between retries.

    Returns
    -------
    result : str
        The standard-out
    """
    logger = ctx["logger"].bind(task="keep_alive")
    logger.info("Running keep_alive")

    jupyter_client = ctx["jupyter_client"]
    exit_msg = ""
    for attempt in range(retries):
        try:
            async with jupyter_client.open_lab_session(
                kernel_name="LSST"
            ) as session:
                await session.run_python("print('alive')")
            break
        except (JupyterWebSocketError, JupyterWebError) as e:
            logger.exception(
                "Error from Jupyter. Forcing worker shutdown",
                jupyter_status=e.status,
                attempt=attempt,
                retries=retries,
            )
            exit_msg = f"{e.status or 'Unknown'} error from Jupyter"
        except Exception:
            logger.exception(
                "keep_alive error", attempt=attempt, retries=retries
            )
            exit_msg = "keep_alive error"

        if attempt + 1 == retries:
            sys.exit(exit_msg)
        await asyncio.sleep(idle.total_seconds())

    return "alive"


def make_keep_alive(retries: int, idle: timedelta) -> WorkerCoroutine:
    """Make a keep-alive coroutine with retry and idle settings.

    Parameters
    ----------
    retries
        The number of times to retry running the code.
    idle
        The amount of time to wait in between retries.

    Returns
    -------
    keep_alive
        A coroutine that can be used as an Arq cron function.
    """

    async def keep_alive(ctx: dict[Any, Any]) -> str:
        return await _keep_alive(ctx, retries, idle)

    return keep_alive
