"""Execute a JupyterNotebook in a JupyterLab pod through the notebook
execution extension.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import timedelta
from typing import Any

from arq import Retry
from rubin.nublado.client.exceptions import NubladoClientSlackException
from safir.slack.blockkit import SlackTextField

from noteburst.exceptions import NbexecTaskError, NbexecTaskTimeoutError


async def nbexec(
    ctx: dict[Any, Any],
    *,
    ipynb: str,
    kernel_name: str = "LSST",
    enable_retry: bool = True,
    timeout: timedelta | None = None,  # noqa: ASYNC109
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
    job_id = ctx.get("job_id", "unknown")
    logger = ctx["logger"].bind(
        task="nbexec",
        job_attempt=ctx.get("job_try", -1),
        job_id=job_id,
        kernel_name=kernel_name,
    )
    logger.debug("Running nbexec")

    jupyter_client = ctx["jupyter_client"]

    async with jupyter_client.open_lab_session(
        notebook_name=job_id, kernel_name=kernel_name
    ) as sess:
        parsed_notebook = json.loads(ipynb)
        logger.debug("Got ipynb", ipynb=parsed_notebook)
        try:
            execution_result = await asyncio.wait_for(
                sess.run_notebook_via_rsp_extension(path=None, content=ipynb),
                timeout=timeout.total_seconds() if timeout else None,
            )
            logger.info("nbexec finished", error=execution_result.error)
        except TimeoutError as e:
            raise NbexecTaskTimeoutError.from_exception(e) from e
        except NubladoClientSlackException as e:
            if hasattr(e, "status"):
                logger.exception("nbexec error", jupyter_status=e.status)
            else:
                logger.exception("nbexec error")
            if "slack" in ctx and "slack_message_factory" in ctx:
                slack_client = ctx["slack"]
                message = e.to_slack()
                message.fields.append(
                    SlackTextField(
                        heading="Job ID", text=ctx.get("job_id", "unknown")
                    )
                )
                message.fields.append(
                    SlackTextField(
                        heading="Attempt",
                        text=str(ctx.get("job_try", "unknown")),
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
                        SlackTextField(
                            heading="Job ID", text=ctx.get("job_id", "unknown")
                        )
                    )
                    message.fields.append(
                        SlackTextField(
                            heading="Attempt",
                            text=str(ctx.get("job_try", "unknown")),
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
