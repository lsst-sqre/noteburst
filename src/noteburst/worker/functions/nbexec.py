"""Execute a JupyterNotebook in a JupyterLab pod through the notebook
execution extension.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import timedelta
from typing import Any, cast

from arq import Retry
from rubin.nublado.client.exceptions import NubladoClientSlackException
from safir.slack.blockkit import SlackTextField

from noteburst.exceptions import NbexecTaskError, NbexecTaskTimeoutError
from noteburst.worker.nublado import NubladoPod


async def nbexec(
    ctx: dict[Any, Any],
    *,
    ipynb: str,
    kernel_name: str = "lsst",
    timeout: timedelta | None = None,
    enable_retry: bool = True,
) -> str:
    """Execute a notebook, as an asynchronous arq worker task.

    Parameters
    ----------
    ctx
        The arq worker context.
    ipynb
        The input Jupyter notebook as a serialized string.
    kernel_name
        The Jupyter kernel to execute the notebook in.
    timeout
        The maximum time to wait for the notebook execution to complete. If
        `None`, no timeout is applied.
    enable_retry
        Whether to retry the notebook execution if it failed.

    Returns
    -------
    str
        The notebook execution result, a JSON-serialized
        `NotebookExecutionResult` object.
    """
    job_id = ctx.get("job_id", "unknown")
    job_try = ctx.get("job_try", 1)
    job_try = cast("int", job_try)

    logger = ctx["logger"].bind(
        task="nbexec",
        job_attempt=job_try,
        job_id=job_id,
        kernel_name=kernel_name,
    )
    logger.debug("Running nbexec", ipynb=ipynb)

    nublado_pod = ctx["nublado_pod"]
    nublado_pod = cast(
        "NubladoPod",
        nublado_pod,
    )

    try:
        execution_result = await asyncio.wait_for(
            nublado_pod.execute_notebook(
                ipynb=ipynb,
                kernel_name=kernel_name,
            ),
            timeout=timeout.total_seconds() if timeout else None,
        )
    except TimeoutError as e:
        raise NbexecTaskTimeoutError.from_exception(e) from e
    except NubladoClientSlackException as e:
        logger.exception(
            "nbexec error", jupyter_status=getattr(e, "status", None)
        )
        if "slack" in ctx:
            slack_client = ctx["slack"]
            message = e.to_slack()
            message.fields.append(
                SlackTextField(heading="Job ID", text=job_id)
            )
            message.fields.append(
                SlackTextField(
                    heading="Attempt",
                    text=str(job_try),
                )
            )
            await slack_client.post(message)

        if hasattr(e, "status") and e.status >= 400 and e.status < 500:
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
                message.fields.append(
                    SlackTextField(heading="Job ID", text=job_id)
                )
                message.fields.append(
                    SlackTextField(
                        heading="Attempt",
                        text=str(job_try),
                    )
                )
                await slack_client.post(message)

            sys.exit("400 class error from Jupyter")

        elif enable_retry:
            logger.warning("nbexec triggering retry")
            raise Retry(defer=job_try * 5) from None

        else:
            raise NbexecTaskError.from_exception(e) from e

    return execution_result.model_dump_json()
