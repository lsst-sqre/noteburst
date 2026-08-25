"""Tests for the Noteburst arq worker settings."""

import pytest
from arq.cron import CronJob
from arq.worker import Function
from pydantic import ValidationError

from noteburst.config.worker import WorkerConfig
from noteburst.worker.main import WorkerSettings
from noteburst.worker.main import config as worker_config


def test_nbexec_job_timeout_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """``nbexec`` has its own arq timeout, long enough that a notebook's own
    ``asyncio.wait_for`` fires before arq's backstop does.
    """
    monkeypatch.delenv("NOTEBURST_WORKER_JOB_TIMEOUT", raising=False)
    monkeypatch.delenv("NOTEBURST_WORKER_NBEXEC_JOB_TIMEOUT", raising=False)

    config = WorkerConfig()

    assert config.nbexec_job_timeout == 3660


def test_nbexec_job_timeout_is_configurable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``NOTEBURST_WORKER_NBEXEC_JOB_TIMEOUT`` sets the nbexec arq timeout."""
    monkeypatch.setenv("NOTEBURST_WORKER_NBEXEC_JOB_TIMEOUT", "7200")

    config = WorkerConfig()

    assert config.nbexec_job_timeout == 7200


@pytest.mark.parametrize("value", ["0", "-1"])
def test_nbexec_job_timeout_rejects_non_positive(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """A zero or negative nbexec timeout is a misconfiguration."""
    monkeypatch.setenv("NOTEBURST_WORKER_NBEXEC_JOB_TIMEOUT", value)

    with pytest.raises(ValidationError):
        WorkerConfig()


def test_worker_registers_nbexec_with_its_own_timeout() -> None:
    """Arq runs ``nbexec`` with a longer timeout than the worker-wide one."""
    nbexec_function = next(
        f
        for f in WorkerSettings.functions
        if isinstance(f, Function) and f.name == "nbexec"
    )

    assert nbexec_function.timeout_s == worker_config.nbexec_job_timeout
    assert nbexec_function.timeout_s > worker_config.job_timeout


def test_job_timeout_defaults_to_short_task_backstop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``job_timeout`` is the backstop for the short worker tasks only.

    Notebook execution has its own, much longer timeout, so this one must
    stay short.
    """
    monkeypatch.delenv("NOTEBURST_WORKER_JOB_TIMEOUT", raising=False)
    monkeypatch.delenv("NOTEBURST_WORKER_NBEXEC_JOB_TIMEOUT", raising=False)

    config = WorkerConfig()

    assert config.job_timeout == 300


def test_short_tasks_use_the_worker_wide_job_timeout() -> None:
    """``ping``, ``run_python``, and the ``keep_alive`` cron have no timeout
    of their own, so arq covers them with the worker-wide ``job_timeout``.

    Asserting the worker-wide value here means a future bump to accommodate
    a long notebook cannot silently widen these tasks' timeouts too.
    """
    assert WorkerSettings.job_timeout == 300

    timed_functions = {
        f.name for f in WorkerSettings.functions if isinstance(f, Function)
    }
    assert timed_functions == {"nbexec"}

    for job in WorkerSettings.cron_jobs:
        assert isinstance(job, CronJob)
        assert job.timeout_s is None
