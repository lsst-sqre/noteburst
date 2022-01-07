"""A FastAPI dependency that supplies a Redis connection for arq."""

from __future__ import annotations

import abc
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from arq import create_pool
from arq.jobs import Job, JobStatus

if TYPE_CHECKING:
    import arq.jobs
    from arq.connections import ArqRedis, RedisSettings


class JobNotQueued(Exception):
    """The job was not successfully queued."""


class JobNotFound(Exception):
    """A job cannot be found."""


class JobResultUnavailable(Exception):
    """The job's result is unavailable."""


class ArqMode(str, Enum):
    """Mode configuration for the Arq queue."""

    production = "production"
    """Normal usage of arq, with a Redis broker."""

    test = "test"
    """Use the MockArqQueue to test an API service without standing up a
    full distributed worker queue.
    """


@dataclass
class JobMetadata:
    """Information about a queued job."""

    id: str
    """The Job identifier."""

    name: str
    """The task name."""

    args: Tuple[Any, ...]
    """The positional arguments to the task function."""

    kwargs: Dict[str, Any]
    """The keyword arguments to the task function."""

    enqueue_time: datetime
    """Time when the job was added to the queue."""

    status: JobStatus
    """Status of the job.

    States are defined by the `arq.jobs.JobStatus` enumeration:

    - ``deferred`` (in queue, but waiting a predetermined time to become
      ready to run)
    - ``queued`` (queued to run)
    - ``in_progress`` (actively being run by a worker)
    - ``complete`` (result is available)
    - ``not_found`` (the job cannot be found)
    """

    @classmethod
    async def from_job(cls, job: arq.jobs.Job) -> JobMetadata:
        """Initialize JobMetadata from an arq Job.

        Raises
        ------
        JobNotFound
            Raised if the job is not found
        """
        job_info = await job.info()
        if job_info is None:
            raise JobNotFound

        job_status = await job.status()
        if job_status == JobStatus.not_found:
            raise JobNotFound

        return cls(
            id=job.job_id,
            name=job_info.function,
            args=job_info.args,
            kwargs=job_info.kwargs,
            enqueue_time=job_info.enqueue_time,
            status=job_status,
        )


@dataclass
class JobResult(JobMetadata):
    """The full result of a job, as well as its metadata."""

    start_time: datetime
    """Time when the job started."""

    finish_time: datetime
    """Time when the job finished."""

    success: bool
    """`True` if the job returned without an exception, `False` if an
    exception was raised.
    """

    result: Any
    """The job's result."""

    @classmethod
    async def from_job(cls, job: arq.jobs.Job) -> JobResult:
        """Initialize JobMetadata from an arq Job.

        Raises
        ------
        JobNotFound
            Raised if the job is not found
        """
        job_info = await job.info()
        if job_info is None:
            raise JobNotFound

        job_status = await job.status()
        if job_status == JobStatus.not_found:
            raise JobNotFound

        # Result may be none if the job isn't finished
        result_info = await job.result_info()
        if result_info is None:
            raise JobResultUnavailable

        return cls(
            id=job.job_id,
            name=job_info.function,
            args=job_info.args,
            kwargs=job_info.kwargs,
            enqueue_time=job_info.enqueue_time,
            start_time=result_info.start_time,
            finish_time=result_info.finish_time,
            success=result_info.success,
            status=job_status,
            result=result_info.result,
        )


class ArqQueue(metaclass=abc.ABCMeta):
    """An common interface for working with an arq queue that can be
    implemented either with a real Redis backend, or an in-memory repository
    for testing.
    """

    @abc.abstractmethod
    async def enqueue(
        self, task_name: str, *task_args: Any, **task_kwargs: Any
    ) -> JobMetadata:
        """Add a job to the queue.

        Parameters
        ----------
        task_name : `str`
            The function name to run.
        *args
            Positional arguments for the task function.
        **kwargs
            Keyword arguments passed to the task function.

        Returns
        -------
        JobMetadata
            Metadata about the queued job.

        Raises
        ------
        JobNotQueued
            Raised if the job is not successfully added to the queue.
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def get_job_metadata(self, job_id: str) -> JobMetadata:
        """Get metadata about a job.

        Parameters
        ----------
        job_id : `str`
            The job's identifier. This is the same as the `JobMetadata.id`
            attribute, provided when initially adding a job to the queue.

        Returns
        -------
        `JobMetadata`
            Metadata about the queued job.

        Raises
        ------
        JobNotFound
            Raised if the job is not found in the queue.
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def get_job_result(self, job_id: str) -> JobResult:
        """The job result, if available.

        Parameters
        ----------
        job_id : `str`
            The job's identifier. This is the same as the `JobMetadata.id`
            attribute, provided when initially adding a job to the queue.

        Returns
        -------
        `JobResult`
            The job's result, along with metadata about the queued job.

        Raises
        ------
        JobNotFound
            Raised if the job is not found in the queue.
        ResultUnavailable
            Raised if the job's result is unavailable for any reason.
        """
        raise NotImplementedError


class RedisArqQueue(ArqQueue):
    """A distributed queue, based on arq and Redis."""

    def __init__(self, pool: ArqRedis) -> None:
        self._pool = pool

    @classmethod
    async def initialize(cls, redis_settings: RedisSettings) -> RedisArqQueue:
        """Initialize a RedisArqQueue from Redis settings."""
        pool = await create_pool(redis_settings)
        return cls(pool)

    async def enqueue(
        self, task_name: str, *task_args: Any, **task_kwargs: Any
    ) -> JobMetadata:
        job = await self._pool.enqueue_job(
            task_name, *task_args, **task_kwargs
        )
        if job:
            return await JobMetadata.from_job(job)
        else:
            raise JobNotQueued

    def _get_job(self, job_id: str) -> Job:
        return Job(job_id, self._pool)

    async def get_job_metadata(self, job_id: str) -> JobMetadata:
        job = self._get_job(job_id)
        return await JobMetadata.from_job(job)

    async def get_job_result(self, job_id: str) -> JobResult:
        job = self._get_job(job_id)
        return await JobResult.from_job(job)


class MockArqQueue(ArqQueue):
    """A mocked queue for testing API services."""

    def __init__(self) -> None:
        self._job_metadata: Dict[str, JobMetadata] = {}
        self._job_results: Dict[str, JobResult] = {}

    async def enqueue(
        self, task_name: str, *task_args: Any, **task_kwargs: Any
    ) -> JobMetadata:
        new_job = JobMetadata(
            id=str(uuid.uuid4().hex),
            name=task_name,
            args=task_args,
            kwargs=task_kwargs,
            enqueue_time=datetime.now(),
            status=JobStatus.queued,
        )
        self._job_metadata[new_job.id] = new_job
        return new_job

    async def get_job_metadata(self, job_id: str) -> JobMetadata:
        try:
            return self._job_metadata[job_id]
        except KeyError:
            raise JobNotFound

    async def get_job_result(self, job_id: str) -> JobResult:
        try:
            return self._job_results[job_id]
        except KeyError:
            raise JobResultUnavailable

    async def set_in_progress(self, job_id: str) -> None:
        """Set a job's status to in progress, for mocking a queue in tests."""
        job = await self.get_job_metadata(job_id)
        job.status = JobStatus.in_progress

        # An in-progress job cannot have a result
        if job_id in self._job_results:
            del self._job_results[job_id]

    async def set_complete(
        self, job_id: str, *, result: Any, success: bool = True
    ) -> None:
        """Set a job's result, for mocking a queue in tests."""
        job_metadata = await self.get_job_metadata(job_id)
        job_metadata.status = JobStatus.complete

        result_info = JobResult(
            id=job_metadata.id,
            name=job_metadata.name,
            args=job_metadata.args,
            kwargs=job_metadata.kwargs,
            status=job_metadata.status,
            enqueue_time=job_metadata.enqueue_time,
            start_time=datetime.now(),
            finish_time=datetime.now(),
            result=result,
            success=success,
        )
        self._job_results[job_id] = result_info


class ArqDependency:
    """A FastAPI dependency that maintains a redis client for enqueing
    tasks to the worker pool.
    """

    def __init__(self) -> None:
        self._arq_queue: Optional[ArqQueue] = None

    async def initialize(
        self, *, mode: ArqMode, redis_settings: Optional[RedisSettings]
    ) -> None:
        if mode == ArqMode.production:
            if not redis_settings:
                raise RuntimeError(
                    "The redis_settings argument must be set for arq in "
                    "production."
                )
            self._arq_queue = await RedisArqQueue.initialize(redis_settings)
        else:
            self._arq_queue = MockArqQueue()

    async def __call__(self) -> ArqQueue:
        if self._arq_queue is None:
            raise RuntimeError("ArqDependency is not initialized")
        return self._arq_queue


arq_dependency = ArqDependency()
"""Singleton instance of ArqDependency that serves as a FastAPI dependency."""
