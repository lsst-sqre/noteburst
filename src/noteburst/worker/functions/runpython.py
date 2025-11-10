"""An Arq worker function to execute Python code in a JupyterLab pod."""

from __future__ import annotations

from typing import Any

from rubin.nublado.client import NubladoClient
from structlog.stdlib import BoundLogger


async def run_python(
    ctx: dict[Any, Any], py: str, *, kernel_name: str = "LSST"
) -> str:
    """Execute Python code in a JupyterLab pod with a specific Jupyter kernel.

    Parameters
    ----------
    ctx
        Arq worker context.
    py
        Python code to execute.
    kernel_name
        Name of the Python kernel.

    Returns
    -------
    str
        The standard-out
    """
    logger: BoundLogger = ctx["logger"].bind(task="run_python")
    nublado_client: NubladoClient = ctx["nublado_client"]

    logger.info("Running run_python", py=py)
    async with nublado_client.lab_session(kernel_name=kernel_name) as session:
        result = await session.run_python(py)

    logger.info("Running run_python", result=result)
    return result
