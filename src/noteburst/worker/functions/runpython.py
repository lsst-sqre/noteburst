from __future__ import annotations

from typing import Any, Dict


async def run_python(
    ctx: Dict[Any, Any], py: str, *, kernel_name: str = "LSST"
) -> str:
    """Execute Python code in a JupyterLab pod with a specific Jupyter kernel.

    Parameters
    ----------
    ctx
        Arq worker context.
    py : str
        Python code to execute.
    kernel_name : str
        Name of the Python kernel.

    Returns
    -------
    result : str
        The standard-out
    """
    logger = ctx["logger"].bind(task="run_python")
    logger.info("Running run_python", py=py)

    jupyter_client = ctx["jupyter_client"]
    async with jupyter_client.open_lab_session(
        kernel_name=kernel_name
    ) as session:
        result = await session.run_python(py)
    logger.info("Running run_python", result=result)

    return result
