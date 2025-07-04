"""Execute Python in the JupyterLab kernel to prevent it from being culled."""

from __future__ import annotations

import sys
from typing import Any, cast

from rubin.nublado.client import NubladoClient
from rubin.nublado.client.exceptions import (
    JupyterWebError,
    JupyterWebSocketError,
)


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
    logger = ctx["logger"].bind(task="keep_alive")

    nublado_client = ctx["nublado_client"]
    nublado_client = cast(
        "NubladoClient",
        nublado_client,
    )

    try:
        async with nublado_client.open_lab_session(
            kernel_name="LSST"
        ) as lab_session:
            return await lab_session.run_python("print('alive')")
    except (JupyterWebSocketError, JupyterWebError) as e:
        if e.status and e.status >= 400 and e.status < 500:
            logger.exception(
                "Authentication error to Jupyter. Forcing worker shutdown",
                jupyter_status=e.status,
            )
        else:
            logger.exception(
                "Jupyter keep_alive error", jupyter_status=e.status
            )
        sys.exit("JupyterLab keepalive error.")
    except Exception as e:
        logger.exception(
            "Unknown keep_alive error", detail=str(e), exception_type=type(e)
        )
        sys.exit("Unknown keepalive error.")
