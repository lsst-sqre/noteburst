"""Mock JupyterHub (and JupyterLab) for testing."""

from __future__ import annotations

import asyncio
import json
import re
from base64 import urlsafe_b64decode
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING, Dict, Optional
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import structlog

from noteburst.config import config
from noteburst.jupyterclient.jupyterlab import JupyterLabSession

if TYPE_CHECKING:
    import respx


class JupyterAction(Enum):
    LOGIN = "login"
    HOME = "home"
    HUB = "hub"
    USER = "user"
    PROGRESS = "progress"
    SPAWN = "spawn"
    SPAWN_PENDING = "spawn_pending"
    LAB = "lab"
    DELETE_LAB = "delete_lab"
    CREATE_SESSION = "create_session"
    DELETE_SESSION = "delete_session"


class JupyterState(Enum):
    LOGGED_OUT = "logged out"
    LOGGED_IN = "logged in"
    SPAWN_PENDING = "spawn pending"
    LAB_RUNNING = "lab running"


def url_for_path(route: str) -> str:
    """Construct a URL for JupyterHub/Proxy."""
    return f"{config.environment_url}/nb/{route}"


def url_for_pattern(route: str) -> str:
    """Construct a URL for JupyterHub/Proxy."""
    prefix = re.escape(f"{config.environment_url}/nb/")
    return prefix + route


class MockJupyter:
    """A mock Jupyter state machine.

    This should be invoked via mocked HTTP calls so that tests can simulate
    making REST calls to the real JupyterHub/Lab.
    """

    def __init__(self) -> None:
        self.sessions: Dict[str, JupyterLabSession] = {}
        self.state: Dict[str, JupyterState] = {}
        self.delete_immediate = True
        self.spawn_timeout = False
        self._delete_at: Dict[str, Optional[datetime]] = {}
        self._fail: Dict[str, Dict[JupyterAction, bool]] = {}

    def fail(self, user: str, action: JupyterAction) -> None:
        """Configure the given action to fail for the given user."""
        if user not in self._fail:
            self._fail[user] = {}
        self._fail[user][action] = True

    def login(self, request: httpx.Request) -> httpx.Response:
        """Mock the JupyterHub log in response."""
        user = self._get_user(request.headers["Authorization"])
        if JupyterAction.LOGIN in self._fail.get(user, {}):
            return httpx.Response(500, request=request)
        state = self.state.get(user, JupyterState.LOGGED_OUT)
        if state == JupyterState.LOGGED_OUT:
            self.state[user] = JupyterState.LOGGED_IN
        return httpx.Response(200, request=request)

    def user(self, request: httpx.Request) -> httpx.Response:
        user = self._get_user(request.headers["Authorization"])
        if JupyterAction.USER in self._fail.get(user, {}):
            return httpx.Response(500, request=request)
        assert str(request.url).endswith(f"/hub/api/users/{user}")
        state = self.state.get(user, JupyterState.LOGGED_OUT)
        if state == JupyterState.SPAWN_PENDING:
            server = {"name": "", "pending": "spawn", "ready": False}
            body = {"name": user, "servers": {"": server}}
        elif state == JupyterState.LAB_RUNNING:
            delete_at = self._delete_at.get(user)
            if delete_at and (datetime.now(tz=timezone.utc)) > delete_at:
                del self._delete_at[user]
                self.state[user] = JupyterState.LOGGED_IN
            if delete_at:
                server = {"name": "", "pending": "delete", "ready": False}
            else:
                server = {"name": "", "pending": None, "ready": True}
            body = {"name": user, "servers": {"": server}}
        else:
            body = {"name": user, "servers": {}}
        return httpx.Response(200, json=body, request=request)

    async def progress(self, request: httpx.Request) -> httpx.Response:
        user = self._get_user(request.headers["Authorization"])
        assert str(request.url).endswith(
            f"/hub/api/users/{user}/server/progress"
        )
        state = self.state.get(user, JupyterState.LOGGED_OUT)
        assert state in (JupyterState.SPAWN_PENDING, JupyterState.LAB_RUNNING)
        if JupyterAction.PROGRESS in self._fail.get(user, {}):
            body = (
                'data: {"progress": 0, "message": "Server requested"}\n'
                'data: {"progress": 50, "message": "Spawning server..."}\n'
                'data: {"progress": 75, "message": "Spawn failed!"}\n'
            )
        elif state == JupyterState.LAB_RUNNING:
            body = (
                'data: {"progress": 100, "ready": true, "message": "Ready"}\n'
            )
        elif self.spawn_timeout:
            # Cause the spawn to time out by pausing for longer than the test
            # should run for and then returning nothing.
            await asyncio.sleep(60)
            body = ""
        else:
            self.state[user] = JupyterState.LAB_RUNNING
            body = (
                'data: {"progress": 0, "message": "Server requested"}\n'
                'data: {"progress": 50, "message": "Spawning server..."}\n'
                'data: {"progress": 100, "ready": true, "message": "Ready"}\n'
            )
        return httpx.Response(200, text=body, request=request)

    def spawn(self, request: httpx.Request) -> httpx.Response:
        user = self._get_user(request.headers["Authorization"])
        if JupyterAction.SPAWN in self._fail.get(user, {}):
            return httpx.Response(500, request=request)
        state = self.state.get(user, JupyterState.LOGGED_OUT)
        assert state == JupyterState.LOGGED_IN
        self.state[user] = JupyterState.SPAWN_PENDING
        return httpx.Response(
            302,
            headers={"Location": url_for_path(f"hub/spawn-pending/{user}")},
            request=request,
        )

    def spawn_pending(self, request: httpx.Request) -> httpx.Response:
        user = self._get_user(request.headers["Authorization"])
        assert str(request.url).endswith(f"/hub/spawn-pending/{user}")
        if JupyterAction.SPAWN_PENDING in self._fail.get(user, {}):
            return httpx.Response(500, request=request)
        state = self.state.get(user, JupyterState.LOGGED_OUT)
        assert state == JupyterState.SPAWN_PENDING
        return httpx.Response(200, request=request)

    def missing_lab(self, request: httpx.Request) -> httpx.Response:
        user = self._get_user(request.headers["Authorization"])
        assert str(request.url).endswith(f"/hub/user/{user}/lab")
        return httpx.Response(503, request=request)

    def lab(self, request: httpx.Request) -> httpx.Response:
        user = self._get_user(request.headers["Authorization"])
        assert str(request.url).endswith(f"/user/{user}/lab")
        if JupyterAction.LAB in self._fail.get(user, {}):
            return httpx.Response(500, request=request)
        state = self.state.get(user, JupyterState.LOGGED_OUT)
        if state == JupyterState.LAB_RUNNING:
            return httpx.Response(200, request=request)
        else:
            return httpx.Response(
                302, headers={"Location": url_for_path(f"hub/user/{user}/lab")}
            )

    def delete_lab(self, request: httpx.Request) -> httpx.Response:
        user = self._get_user(request.headers["Authorization"])
        assert str(request.url).endswith(f"/users/{user}/server")
        if JupyterAction.DELETE_LAB in self._fail.get(user, {}):
            return httpx.Response(500, request=request)
        state = self.state.get(user, JupyterState.LOGGED_OUT)
        assert state != JupyterState.LOGGED_OUT
        if self.delete_immediate:
            self.state[user] = JupyterState.LOGGED_IN
        else:
            now = datetime.now(tz=timezone.utc)
            self._delete_at[user] = now + timedelta(seconds=5)
        return httpx.Response(202, request=request)

    def create_session(self, request: httpx.Request) -> httpx.Response:
        user = self._get_user(request.headers["Authorization"])
        assert str(request.url).endswith(f"/user/{user}/api/sessions")
        assert user not in self.sessions
        if JupyterAction.CREATE_SESSION in self._fail.get(user, {}):
            return httpx.Response(500, request=request)
        state = self.state.get(user, JupyterState.LOGGED_OUT)
        assert state == JupyterState.LAB_RUNNING
        request_json = json.loads(request.content.decode("utf-8"))
        assert request_json["kernel"]["name"] == "LSST"
        assert request_json["name"] == "(no notebook)"
        assert request_json["type"] == "console"
        session = JupyterLabSession(
            username=user,
            session_id=uuid4().hex,
            kernel_id=uuid4().hex,
            websocket=AsyncMock(),
            logger=structlog.get_logger(),
        )
        self.sessions[user] = session
        return httpx.Response(
            201,
            json={
                "id": session.session_id,
                "kernel": {"id": session.kernel_id},
            },
            request=request,
        )

    def delete_session(self, request: httpx.Request) -> httpx.Response:
        user = self._get_user(request.headers["Authorization"])
        session_id = self.sessions[user].session_id
        assert str(request.url).endswith(
            f"/user/{user}/api/sessions/{session_id}"
        )
        if JupyterAction.DELETE_SESSION in self._fail.get(user, {}):
            return httpx.Response(500, request=request)
        state = self.state.get(user, JupyterState.LOGGED_OUT)
        assert state == JupyterState.LAB_RUNNING
        del self.sessions[user]
        return httpx.Response(204, request=request)

    @staticmethod
    def _get_user(authorization: str) -> str:
        """Get the user from the Authorization header."""
        assert authorization.startswith("Bearer ")
        token = authorization.split(" ", 1)[1]
        user = urlsafe_b64decode(token[3:].split(".", 1)[0].encode())
        return user.decode()


def mock_jupyter(mock_router: respx.Router) -> MockJupyter:
    """Set up a mock JupyterHub/Lab that always returns success.

    Currently only handles a lab spawn and then shutdown.  Behavior will
    eventually be configurable.
    """
    mock = MockJupyter()

    mock_router.get(url_for_path("hub/login")).mock(side_effect=mock.login)
    mock_router.get(url_for_path("hub/spawn"))
    mock_router.post(url_for_path("hub/spawn")).mock(side_effect=mock.spawn)

    mock_router.get(
        url__regex=url_for_pattern(r"hub/spawn-pending/[^/]+$")
    ).mock(side_effect=mock.spawn_pending)

    mock_router.get(url__regex=url_for_pattern(r"hub/user/[^/]+/lab$")).mock(
        side_effect=mock.missing_lab
    )

    mock_router.get(url__regex=url_for_pattern(r"hub/api/users/[^/]+$")).mock(
        side_effect=mock.user
    )

    mock_router.get(
        url__regex=url_for_pattern(r"hub/api/users/[^/]+/server/progress$")
    ).mock(side_effect=mock.progress)

    mock_router.delete(
        url__regex=url_for_pattern(r"hub/api/users/[^/]+/server")
    ).mock(side_effect=mock.delete_lab)

    mock_router.get(url__regex=url_for_pattern(r"user/[^/]+/lab")).mock(
        side_effect=mock.lab
    )

    mock_router.post(
        url__regex=url_for_pattern(r"user/[^/]+/api/sessions")
    ).mock(side_effect=mock.create_session)

    mock_router.delete(
        url__regex=url_for_pattern(r"user/[^/]+/api/sessions/[^/]+$"),
    ).mock(side_effect=mock.delete_session)

    return mock
