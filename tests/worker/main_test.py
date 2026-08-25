"""Tests for the Noteburst arq worker settings."""

import pytest
from arq.worker import Function

from noteburst.config.worker import WorkerConfig
from noteburst.worker.main import WorkerSettings
from noteburst.worker.main import config as worker_config


def test_nbexec_job_timeout_adds_grace_margin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The arq backstop for ``nbexec`` is the worker job timeout plus a
    grace margin, so a notebook's own ``asyncio.wait_for`` fires first.
    """
    monkeypatch.setenv("NOTEBURST_WORKER_JOB_TIMEOUT", "300")
    monkeypatch.delenv("NOTEBURST_JOB_TIMEOUT_GRACE", raising=False)

    config = WorkerConfig()

    assert config.job_timeout_grace == 60
    assert config.nbexec_job_timeout == 360


def test_job_timeout_grace_is_configurable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``NOTEBURST_JOB_TIMEOUT_GRACE`` sets the grace margin."""
    monkeypatch.setenv("NOTEBURST_WORKER_JOB_TIMEOUT", "3600")
    monkeypatch.setenv("NOTEBURST_JOB_TIMEOUT_GRACE", "120")

    config = WorkerConfig()

    assert config.job_timeout_grace == 120
    assert config.nbexec_job_timeout == 3720


def test_worker_registers_nbexec_with_its_own_timeout() -> None:
    """Arq runs ``nbexec`` with a longer timeout than the worker-wide one."""
    nbexec_function = next(
        f
        for f in WorkerSettings.functions
        if isinstance(f, Function) and f.name == "nbexec"
    )

    assert nbexec_function.timeout_s == worker_config.nbexec_job_timeout
    assert nbexec_function.timeout_s > worker_config.job_timeout


def test_job_timeout_defaults_to_backstop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``job_timeout`` defaults to an hour: it is a worker backstop, not the
    notebook execution limit, which the client supplies per request.
    """
    monkeypatch.delenv("NOTEBURST_WORKER_JOB_TIMEOUT", raising=False)
    monkeypatch.delenv("NOTEBURST_JOB_TIMEOUT_GRACE", raising=False)

    config = WorkerConfig()

    assert config.job_timeout == 3600
    assert config.nbexec_job_timeout == 3660
