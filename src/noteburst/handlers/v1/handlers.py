"""V1 REST API handlers."""

import structlog
from fastapi import APIRouter, Depends, Request
from safir.dependencies.logger import logger_dependency

from noteburst.dependencies.arqpool import ArqQueue, arq_dependency

from .models import PostNbexecRequest, QueuedNbexecJob, QueuedNbexecJobResult

v1_router = APIRouter(tags=["v1"])
"""FastAPI router for the /v1/ REST API"""


@v1_router.post(
    "/",
    description=(
        "Execute a Jupyter notebook, asynchronously via a pool of JupyterLab "
        "instances."
    ),
    status_code=202,
    response_model=QueuedNbexecJob,
    response_model_exclude_none=True,
)
async def post_nbexec(
    request_data: PostNbexecRequest,
    *,
    request: Request,
    logger: structlog.BoundLogger = Depends(logger_dependency),
    arq_queue: ArqQueue = Depends(arq_dependency),
) -> QueuedNbexecJob:
    logger.debug("Enqueing a nbexec task")
    job_metadata = await arq_queue.enqueue(
        "nbexec",
        ipynb=request_data.get_ipynb_as_str(),
        kernel_name=request_data.kernel_name,
    )
    logger.info("Finished enqueing an nbexec task", job_id=job_metadata.id)
    return await QueuedNbexecJob.from_job_metadata(
        job=job_metadata, request=request
    )


@v1_router.get(
    "/jobs/{job_id}",
    description="Get information about a notebook execution job.",
    response_model=QueuedNbexecJob,
    response_model_exclude_none=True,
)
async def get_nbexec_job(
    *,
    job_id: str,
    request: Request,
    ipynb: bool = False,
    logger: structlog.BoundLogger = Depends(logger_dependency),
    arq_queue: ArqQueue = Depends(arq_dependency),
) -> QueuedNbexecJob:
    job_metadata = await arq_queue.get_job_metadata(job_id)
    return await QueuedNbexecJob.from_job_metadata(
        job=job_metadata, request=request, include_ipynb=ipynb
    )


@v1_router.get(
    "/jobs/{job_id}/result",
    response_model=QueuedNbexecJobResult,
    description="Get the result from a completed notebook execution job.",
)
async def get_nbexec_job_result(
    *,
    job_id: str,
    request: Request,
    logger: structlog.BoundLogger = Depends(logger_dependency),
    arq_queue: ArqQueue = Depends(arq_dependency),
) -> QueuedNbexecJobResult:
    job_result = await arq_queue.get_job_result(job_id)
    return await QueuedNbexecJobResult.from_job_result(
        job=job_result, request=request
    )
