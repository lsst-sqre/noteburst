"""An Arq worker function to execute Python code in a JupyterLab pod."""

from __future__ import annotations

from typing import Any, cast

from rubin.nublado.client import NubladoClient


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
    logger = ctx["logger"].bind(task="run_python")
    logger.info("Running run_python", py=py)

    nublado_client = ctx["nublado_client"]
    nublado_client = cast(
        "NubladoClient",
        nublado_client,
    )

    async with nublado_client.open_lab_session(
        kernel_name=kernel_name
    ) as lab_session:
        result = await lab_session.run_python(py)
    logger.info("Running run_python", result=result)

    return result
