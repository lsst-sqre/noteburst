"""Execute Python in the JupyterLab kernel to prevent it from being culled."""

from __future__ import annotations

import sys
from typing import Any

from rubin.nublado.client.exceptions import JupyterWebSocketError


async def keep_alive(ctx: dict[Any, Any]) -> str:
    """Execute Python code in a JupyterLab pod with a specific Jupyter kernel.

    Parameters
    ----------
    ctx
        Arq worker context.

    Returns
    -------
    result : str
        The standard-out
    """
    logger = ctx["logger"].bind(task="keep_alive")
    logger.info("Running keep_alive")

    jupyter_client = ctx["jupyter_client"]
    try:
        async with jupyter_client.open_lab_session(
            kernel_name="LSST"
        ) as session:
            await session.run_python("print('alive')")
    except JupyterWebSocketError as e:
        logger.exception("keep_alive error", jupyter_status=e.status)
        if e.status and e.status >= 400 and e.status < 500:
            logger.exception(
                "Authentication error to Jupyter. Forcing worker shutdown",
                jupyter_status=e.status,
            )
            sys.exit("400 class error from Jupyter")

    return "alive"
