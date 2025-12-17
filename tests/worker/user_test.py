"""Tests for the noteburst.worker.user module."""

from __future__ import annotations

import pytest
import respx
from rubin.gafaelfawr import GafaelfawrClient, GafaelfawrUserInfo

from noteburst.config.frontend import config
from noteburst.worker.user import User


@pytest.mark.asyncio
async def test_generate_token(respx_mock: respx.Router) -> None:
    token = config.gafaelfawr_token.get_secret_value()
    u = User(username="bot-someuser", uid=1234, gid=5678)
    scopes = ["exec:notebook"]

    gafaelfawr = GafaelfawrClient()
    user = await u.login(
        scopes=scopes, gafaelfawr_client=gafaelfawr, token_lifetime=3600
    )
    assert user.username == "bot-someuser"
    assert user.uid == 1234
    assert user.gid == 5678
    assert user.scopes == ["exec:notebook"]
    assert user.token.startswith("gt-")

    userinfo = await gafaelfawr.get_user_info(token, "bot-someuser")
    assert userinfo == GafaelfawrUserInfo(
        username="bot-someuser", name="Noteburst", uid=1234, gid=5678
    )
