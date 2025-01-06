"""V1 REST API handlers."""

from typing import Annotated

import structlog
from arq.jobs import JobStatus
from fastapi import APIRouter, Depends, Query, Request, Response
from safir.arq import ArqQueue, JobNotFound
from safir.dependencies.arq import arq_dependency
from safir.dependencies.gafaelfawr import (
    auth_dependency,
    auth_logger_dependency,
)
from safir.models import ErrorLocation, ErrorModel
from safir.slack.webhook import SlackRouteErrorHandler

from noteburst.exceptions import JobNotFoundError, NoteburstJobError

from .models import NotebookResponse, PostNotebookRequest

v1_router = APIRouter(tags=["v1"], route_class=SlackRouteErrorHandler)
"""FastAPI router for the /v1/ REST API"""


@v1_router.post(
    "/notebooks/",
    summary="Submit a notebook for execution",
    status_code=202,
    response_model_exclude_none=True,
)
async def post_nbexec(
    request_data: PostNotebookRequest,
    *,
    request: Request,
    response: Response,
    logger: Annotated[structlog.BoundLogger, Depends(auth_logger_dependency)],
    arq_queue: Annotated[ArqQueue, Depends(arq_dependency)],
) -> NotebookResponse:
    """Submits a notebook for execution. The notebook is executed
    asynchronously via a pool of JupyterLab (Nublado) instances.

    ### Configuring how the notebook is run

    The JupyterLab kernel can be set via the optional `kernel_name` field.
    The default kernel is `LSST`, which is a Python 3 kernel that includes
    the full Rubin Python environment
    ([rubinenv](https://github.com/conda-forge/rubinenv-feedstock)).

    Note that you cannot specify some aspects of the JupyterLab pod that
    the notebook is run on:

    - The user identity (a generic account is used)
    - The Nublado version
    - The machine size

    ### Getting the notebook status and result

    The JSON response body includes a `self_url` field (the same value is also
    available in the `Location` response header). You can send a
    `GET` request to this URL to get metadata about the execution job
    and (if available) the notebook (`ipynb`) result. See
    `GET /v1/notebooks/{job_id}` for more information.
    """
    logger.debug("Enqueing a nbexec task")
    job_metadata = await arq_queue.enqueue(
        "nbexec",
        ipynb=request_data.get_ipynb_as_str(),
        kernel_name=request_data.kernel_name,
        enable_retry=request_data.enable_retry,
        timeout=request_data.timeout,
    )
    logger.info("Finished enqueing an nbexec task", job_id=job_metadata.id)
    response_data = await NotebookResponse.from_job_metadata(
        job=job_metadata, request=request
    )
    response.headers["Location"] = str(response_data.self_url)
    return response_data


@v1_router.get(
    "/notebooks/{job_id}",
    summary="Get information about a notebook execution job",
    response_model_exclude_none=True,
    responses={404: {"description": "Not found", "model": ErrorModel}},
)
async def get_nbexec_job(
    *,
    job_id: str,
    request: Request,
    source: Annotated[
        bool,
        Query(
            title="Include source ipynb",
            description=(
                "If set to true, the `source` field will include the "
                "JSON-encoded content of the source ipynb notebook."
            ),
        ),
    ] = False,
    result: Annotated[
        bool,
        Query(
            title="Include the result",
            description=(
                "If set to true and the notebook run is complete, the "
                "response includes the executed notebook and metadata about "
                "the run."
            ),
        ),
    ] = True,
    logger: Annotated[structlog.BoundLogger, Depends(auth_logger_dependency)],
    user: Annotated[str, Depends(auth_dependency)],
    arq_queue: Annotated[ArqQueue, Depends(arq_dependency)],
) -> NotebookResponse:
    """Provides information about a notebook execution job, and the result
    (if available).

    ### Information from a completed notebook

    Many response fields are only included when the result is available
    (the `status` field is `complete`):

    - `ipynb` (the JSON-included executed Jupyter notebook)
    - `start_time`
    - `finish_time`
    - `success`

    If you do not require these fields, regardless of the `status`, you can
    set the `result=false` URL query parameter. This speeds up the response
    slightly.

    ### Toggling inclusion of the source notebook

    If you require the notebook that was originally submitted, set the
    URL query parameter `source=true`.
    """
    try:
        job_metadata = await arq_queue.get_job_metadata(job_id)
    except JobNotFound:
        raise JobNotFoundError(
            "Job not found", location=ErrorLocation.path, field_path=["job_id"]
        ) from None
    except Exception as e:
        raise NoteburstJobError(
            "Error getting job metadata",
            user=user,
            job_id=job_id,
        ) from e
    logger.debug(
        "Got nbexec job metadata",
        job_id=job_id,
        job_metadata=job_metadata,
        status=job_metadata.status,
    )

    if result and job_metadata.status == JobStatus.complete:
        try:
            job_result = await arq_queue.get_job_result(job_id)
        except JobNotFound:
            raise JobNotFoundError(
                "Job not found",
                location=ErrorLocation.path,
                field_path=["job_id"],
            ) from None
        except Exception as e:
            raise NoteburstJobError(
                "Error getting nbexec job result",
                user=user,
                job_id=job_id,
            ) from e
        logger.debug(
            "Got nbexec job result",
            job_id=job_id,
            job_result=job_result,
            success=job_result.success,
            status=job_result.status,
        )
    else:
        job_result = None

    return await NotebookResponse.from_job_metadata(
        job=job_metadata,
        request=request,
        include_source=source,
        job_result=job_result,
    )
