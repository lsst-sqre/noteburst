"""Tests for the noteburst.worker.user module."""

from __future__ import annotations

import httpx
import pytest
import respx

from noteburst.worker.user import User
from tests.support.gafaelfawr import mock_gafaelfawr


@pytest.mark.asyncio
async def test_generate_token(respx_mock: respx.Router) -> None:
    u = User(username="someuser", uid=1234, gid=5678)
    mock_gafaelfawr(respx_mock, u.username, u.uid, u.gid)
    scopes = ["exec:notebook"]

    async with httpx.AsyncClient() as http_client:
        user = await u.login(
            scopes=scopes, http_client=http_client, token_lifetime=3600
        )
    assert user.username == "someuser"
    assert user.uid == 1234
    assert user.gid == 5678
    assert user.scopes == ["exec:notebook"]
    assert user.token.startswith("gt-")
