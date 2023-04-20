"""Execute a JupyterNotebook in a JupyterLab pod through the notebook
execution extension.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from arq import Retry

from noteburst.exceptions import NbexecTaskError
from noteburst.jupyterclient.jupyterlab import JupyterError


async def nbexec(
    ctx: dict[Any, Any],
    *,
    ipynb: str,
    kernel_name: str = "LSST",
    enable_retry: bool = True,
) -> str:
    """Execute a notebook, as an asynchronous arq worker task.

    Parameters
    ----------
    ctx : `dict`
        The arq worker context.
    ipynb : `str`
        The input Jupyter notebook as a serialized string.
    kernel_name : `str`
        The Jupyter kernel to execute the notebook in.
    enable_retry : `bool`
        Whether to retry the notebook execution if it failed.

    Returns
    -------
    str
        The executed Jupyter notebook (ipynb) as a serialized JSON string.
    """
    logger = ctx["logger"].bind(
        task="nbexec", job_attempt=ctx.get("job_try", -1)
    )
    logger.info("Running nbexec")

    jupyter_client = ctx["jupyter_client"]

    parsed_notebook = json.loads(ipynb)
    logger.debug("Got ipynb", ipynb=parsed_notebook)
    try:
        executed_notebook = await jupyter_client.execute_notebook(
            parsed_notebook, kernel_name=kernel_name
        )
        logger.debug("nbexec success")
    except JupyterError as e:
        logger.error("nbexec error", jupyter_status=e.status)
        if e.status >= 400 and e.status < 500:
            logger.error(
                "Authentication error to Jupyter. Forcing worker shutdown",
                jupyter_status=e.status,
            )
            sys.exit("400 class error from Jupyter")
        else:
            # trigger re-try with increasing back-off
            if enable_retry:
                logger.warning("Triggering retry")
                raise Retry(defer=ctx["job_try"] * 5)
            else:
                raise NbexecTaskError.from_exception(e)

    return json.dumps(executed_notebook)
