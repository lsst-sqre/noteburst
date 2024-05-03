"""Mock Gafaelfawr service."""

from __future__ import annotations

import base64
import json
import os
import time
from unittest.mock import ANY
from urllib.parse import urljoin

import httpx
import respx

from noteburst.config import config

__all__ = ["make_gafaelfawr_token", "mock_gafaelfawr"]


def make_gafaelfawr_token(username: str | None = None) -> str:
    """Create a random or user Gafaelfawr token.

    If a username is given, embed the username in the key portion of the token
    so that we can extract it later.  This means the token no longer follows
    the format of a valid Gafaelfawr token, but it lets the mock JupyterHub
    know what user is being authenticated.
    """
    if username:
        key = base64.urlsafe_b64encode(username.encode()).decode()
    else:
        key = base64.urlsafe_b64encode(os.urandom(16)).decode().rstrip("=")
    secret = base64.urlsafe_b64encode(os.urandom(16)).decode().rstrip("=")
    return f"gt-{key}.{secret}"


def mock_gafaelfawr(
    respx_mock: respx.Router,
    username: str | None = None,
    uid: int | None = None,
    gid: int | None = None,
) -> None:
    """Mock out the call to Gafaelfawr ``/auth/api/v1/tokens`` endpoint to
    create a user token.

    Optionally verifies that the username and UID provided to Gafaelfawr are
    correct.
    """
    admin_token = config.gafaelfawr_token.get_secret_value()
    assert admin_token
    assert admin_token.startswith("gt-")

    def handler(request: httpx.Request) -> httpx.Response:
        request_json = json.loads(request.content.decode("utf-8"))
        # Note httpx.Request seems to obfuscate the authorization header
        # so we can't check it here.
        assert request_json == {
            "username": ANY,
            "token_type": "service",
            "scopes": ["exec:notebook"],
            "expires": ANY,
            "name": "Noteburst",
            "uid": ANY,
            "gid": ANY,
        }
        if username:
            assert request_json["username"] == username
        if uid:
            assert request_json["uid"] == uid
        if gid:
            assert request_json["gid"] == gid
        assert request_json["token_name"].startswith("noteburst ")
        assert request_json["expires"] > time.time()
        response = {"token": make_gafaelfawr_token(request_json["username"])}
        return httpx.Response(200, json=response, request=request)

    mock_url = urljoin(f"{config.environment_url}", "/auth/api/v1/tokens")
    print(mock_url)
    respx_mock.post(mock_url).mock(side_effect=handler)
