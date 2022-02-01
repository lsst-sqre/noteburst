"""Execute a JupyterNotebook in a JupyterLab pod through the notebook
execution extension.
"""

from __future__ import annotations

import json
from typing import Any, Dict


async def nbexec(
    ctx: Dict[Any, Any], ipynb: str, *, kernel_name: str = "LSST"
) -> str:
    logger = ctx["logger"].bind(task="nbexec")
    logger.info("Running nbexec")

    jupyter_client = ctx["jupyter_client"]

    parsed_notebook = json.loads(ipynb)
    logger.debug("Got ipynb", ipynb=parsed_notebook)
    executed_notebook = await jupyter_client.execute_notebook(
        parsed_notebook, kernel_name=kernel_name
    )

    return json.dumps(executed_notebook)
