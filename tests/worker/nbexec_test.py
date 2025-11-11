"""Test the ``nbexec`` worker function."""

from __future__ import annotations

from typing import Any

import pytest
from rubin.nublado.client import (
    MockJupyter,
    NotebookExecutionError,
    NotebookExecutionResult,
)

from noteburst.worker.functions.nbexec import nbexec
from noteburst.worker.identity import IdentityModel


@pytest.mark.asyncio
async def test_nbexec(
    worker_context: dict[Any, Any],
    mock_jupyter: MockJupyter,
    sample_ipynb: str,
    sample_ipynb_executed: str,
) -> None:
    identity: IdentityModel = worker_context["identity"]
    username = identity.username

    expected = NotebookExecutionResult(notebook=sample_ipynb_executed)
    mock_jupyter.register_notebook_result(sample_ipynb, expected)

    result = await nbexec(worker_context, ipynb=sample_ipynb)
    parsed_result = NotebookExecutionResult.model_validate_json(result)
    assert parsed_result == expected
    assert mock_jupyter.get_last_notebook_kernel(username) == "LSST"

    result = await nbexec(
        worker_context, ipynb=sample_ipynb, kernel_name="Custom"
    )
    parsed_result = NotebookExecutionResult.model_validate_json(result)
    assert parsed_result == expected
    assert mock_jupyter.get_last_notebook_kernel(username) == "Custom"


@pytest.mark.asyncio
async def test_nbexec_error(
    worker_context: dict[Any, Any],
    mock_jupyter: MockJupyter,
    sample_ipynb: str,
    sample_ipynb_executed: str,
) -> None:
    expected = NotebookExecutionResult(
        notebook=sample_ipynb_executed,
        error=NotebookExecutionError(
            name="ZeroDivisionError",
            value="1 / 0",
            message="Division by zero",
            traceback="some traceback",
        ),
    )
    mock_jupyter.register_notebook_result(sample_ipynb, expected)

    result = await nbexec(worker_context, ipynb=sample_ipynb)
    parsed_result = NotebookExecutionResult.model_validate_json(result)
    assert parsed_result == expected
