"""Execute Python in the JupyterLab kernel to prevent it from being culled."""

from __future__ import annotations

import sys
from typing import Any

from rubin.nublado.client import NubladoClient, NubladoWebError
from structlog.stdlib import BoundLogger


async def keep_alive(ctx: dict[Any, Any]) -> str:
    """Execute Python code in a JupyterLab pod with a specific Jupyter kernel.

    Parameters
    ----------
    ctx
        Arq worker context.

    Returns
    -------
    result
        The standard-out.
    """
    logger: BoundLogger = ctx["logger"].bind(task="keep_alive")
    nublado_client: NubladoClient = ctx["nublado_client"]

    try:
        await nublado_client.auth_to_lab()
        async with nublado_client.lab_session() as session:
            return await session.run_python("print('alive')")
    except NubladoWebError as e:
        logger = logger.bind(jupyter_status=e.status)
        if e.status and e.status >= 400 and e.status < 500:
            msg = "Authentication error to Jupyter. Forcing worker shutdown."
            logger.exception(msg)
        else:
            logger.exception("Jupyter keep_alive error")
        sys.exit("JupyterLab keepalive error.")
    except Exception as e:
        logger.exception(
            "Unknown keep_alive error.", detail=str(e), exception_type=type(e)
        )
        sys.exit("Unknown keepalive error.")
