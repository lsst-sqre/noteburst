"""Execute a JupyterNotebook in a JupyterLab pod through the notebook
execution extension.
"""

from __future__ import annotations

import json
import sys
from typing import Any, cast

from arq import Retry
from safir.slack.blockkit import SlackCodeBlock, SlackTextField

from noteburst.exceptions import NbexecTaskError
from noteburst.jupyterclient.jupyterlab import JupyterClient, JupyterError


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
        The notebook execution result, a JSON-serialized
        `NotebookExecutionResult` object.
    """
    logger = ctx["logger"].bind(
        task="nbexec",
        job_attempt=ctx.get("job_try", -1),
        job_id=ctx.get("job_id", "unknown"),
        kernel_name=kernel_name,
    )
    logger.debug("Running nbexec")

    jupyter_client = cast(JupyterClient, ctx["jupyter_client"])

    parsed_notebook = json.loads(ipynb)
    logger.debug("Got ipynb", ipynb=parsed_notebook)
    try:
        execution_result = await jupyter_client.execute_notebook(
            parsed_notebook, kernel_name=kernel_name
        )
        logger.info("nbexec finished", error=execution_result.error)
    except JupyterError as e:
        logger.exception("nbexec error", jupyter_status=e.status)
        if "slack" in ctx and "slack_message_factory" in ctx:
            slack_client = ctx["slack"]
            message = ctx["slack_message_factory"]("Nbexec failed.")
            message.blocks.append(
                SlackCodeBlock(heading="Exception", code=str(e))
            )
            message.fields.append(
                SlackTextField(heading="Jupyter response", text=str(e.status))
            )
            message.fields.append(
                SlackTextField(
                    heading="Job ID", text=ctx.get("job_id", "unknown")
                )
            )
            message.fields.append(
                SlackTextField(
                    heading="Attempt", text=ctx.get("job_try", "unknown")
                )
            )
            message.blocks.append(
                SlackCodeBlock(heading="Notebook", code=ipynb)
            )
            await slack_client.post(message)

        if e.status >= 400 and e.status < 500:
            logger.exception(
                "Authentication error to Jupyter. Forcing worker shutdown",
                jupyter_status=e.status,
            )

            if "slack" in ctx and "slack_message_factory" in ctx:
                slack_client = ctx["slack"]
                message = ctx["slack_message_factory"](
                    "Noteburst worker shutting down due to Jupyter "
                    "authentication error during nbexec."
                )
                message.blocks.append(
                    SlackCodeBlock(heading="Exception", code=str(e))
                )
                message.fields.append(
                    SlackTextField(
                        heading="Jupyter response", text=str(e.status)
                    )
                )
                message.fields.append(
                    SlackTextField(
                        heading="Job ID", text=ctx.get("job_id", "unknown")
                    )
                )
                message.fields.append(
                    SlackTextField(
                        heading="Attempt", text=ctx.get("job_try", "unknown")
                    )
                )
                await slack_client.post(message)

            sys.exit("400 class error from Jupyter")
        elif enable_retry:
            logger.warning("nbexec triggering retry")
            raise Retry(defer=ctx["job_try"] * 5) from None
        else:
            raise NbexecTaskError.from_exception(e) from e

    return execution_result.model_dump_json()
