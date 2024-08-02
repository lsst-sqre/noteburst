"""Client for JupyterLab through the JupyterHub."""

from __future__ import annotations

import asyncio
import contextlib
import datetime
import json
from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass
from typing import Annotated, Any
from urllib.parse import urljoin, urlparse
from uuid import uuid4

import httpx
import websockets
from httpx import Cookies, Response, Timeout
from pydantic import BaseModel, Field
from structlog import BoundLogger
from websockets.client import WebSocketClientProtocol
from websockets.exceptions import WebSocketException
from websockets.typing import Data as WebsocketData

from noteburst.config import JupyterImageSelector
from noteburst.config import config as noteburst_config

from .labcontroller import JupyterImage, LabControllerClient
from .user import AuthenticatedUser

__all__ = [
    "SpawnProgressMessage",
    "JupyterSpawnProgress",
    "JupyterLabSession",
    "JupyterConfig",
    "JupyterError",
    "JupyterLabSessionError",
    "JupyterClient",
]


@dataclass(frozen=True)
class SpawnProgressMessage:
    """A progress message from JupyterLab spawning."""

    progress: int
    """Percentage progress on spawning."""

    message: str
    """A progress message."""

    ready: bool
    """Whether the server is ready."""


class JupyterSpawnProgress:
    """Provides status and polling of lab spawn progress.

    This wraps an ongoing call to the progress API, which is an EventStream
    API that provides status messages for a spawning lab.
    """

    def __init__(self, response: httpx.Response, logger: BoundLogger) -> None:
        self._response = response
        self._logger = logger
        self._start = datetime.datetime.now(tz=datetime.UTC)

    async def __aiter__(self) -> AsyncIterator[SpawnProgressMessage]:
        """Iterate over spawn progress events."""
        prefix = "data:"
        prefix_length = len(prefix)

        async for line in self._response.aiter_lines():
            if not line.startswith(prefix):
                continue
            raw_event = line[prefix_length:].strip()

            # Parse the valid event
            try:
                event_dict = json.loads(raw_event)
                event = SpawnProgressMessage(
                    progress=event_dict["progress"],
                    message=event_dict["message"],
                    ready=event_dict.get("ready", False),
                )
            except Exception as e:
                msg = f"Ignoring invalid progress event: {raw_event}: {e!s}"
                self._logger.warning(
                    msg, raw_event=raw_event, exception=str(e)
                )
                continue

            # Log and yield the event
            now = datetime.datetime.now(tz=datetime.UTC)
            elapsed = int((now - self._start).total_seconds())
            status = "complete" if event.ready else "in progress"
            self._logger.info(
                "Spawning",
                status=status,
                elapsed=elapsed,
                details=event.message,
            )
            yield event


@dataclass
class WebSocketMessageOutput:
    """The incremental output from a JupyterLab websocket."""

    content: str
    """The content from the websocket message."""

    done: bool
    """This flag is `True` if there are no further messages."""


@dataclass(frozen=True)
class JupyterLabSession:
    """Represents an open session with a JupyterLab.

    This holds the information a client needs to talk to JupyterLab in order to
    execute code.
    """

    username: str
    session_id: str
    kernel_id: str
    websocket: WebSocketClientProtocol
    logger: BoundLogger

    async def run_python(self, code: str) -> str:
        """Run a Python code in the JupyterLab kernel."""
        msg_id = uuid4().hex
        msg = {
            "header": {
                "username": self.username,
                "version": "5.0",
                "session": self.session_id,
                "msg_id": msg_id,
                "msg_type": "execute_request",
            },
            "parent_header": {},
            "channel": "shell",
            "content": {
                "code": code,
                "silent": False,
                "store_history": False,
                "user_expressions": {},
                "allow_stdin": False,
            },
            "metadata": {},
            "buffers": {},
        }

        await self.websocket.send(json.dumps(msg))

        result = ""
        async for message in self.websocket:
            try:
                parsed_message = await self._process_run_python_message(
                    message, msg_id, code
                )
                result += parsed_message.content
                if parsed_message.done:
                    break
            except CodeExecutionError as e:
                if result:
                    e.result = result
                raise

        return result

    async def _process_run_python_message(
        self, raw_message: WebsocketData, msg_id: str, code: str
    ) -> WebSocketMessageOutput:
        """Process an individual message received from the websocket,
        initiated from `run_python`.

        This method returns incremental fragments of the result string. If
        the message is an ``execute_reply`` with status of ``ok``, then this
        method toggles the ``done`` attribute of the returned
        `WebSocketMessageOutput` to done.
        """
        if isinstance(raw_message, bytes):
            raw_text = raw_message.decode("utf-8")
        else:
            raw_text = raw_message
        response_data = json.loads(raw_text)

        self.logger.debug(f"Received kernel message: {response_data}")
        msg_type = response_data["msg_type"]

        if response_data.get("parent_header", {}).get("msg_id") != msg_id:
            # Ignore messages not intended for us. The web socket is
            # rather chatty with broadcast status messages.
            return WebSocketMessageOutput(content="", done=False)
        elif msg_type == "error":
            error = "".join(response_data["content"]["traceback"])
            raise CodeExecutionError(
                username=self.username, code=code, error=error
            )
        elif msg_type == "stream":
            return WebSocketMessageOutput(
                content=response_data["content"]["text"], done=False
            )
        elif msg_type == "execute_reply":
            status = response_data["content"]["status"]
            if status == "ok":
                return WebSocketMessageOutput(content="", done=True)
            else:
                raise CodeExecutionError(
                    username=self.username, code=code, status=status
                )
        elif msg_type == "status":
            # Ignore status messages
            return WebSocketMessageOutput(content="", done=False)
        elif msg_type == "execute_input":
            # Ignore execute input messages
            return WebSocketMessageOutput(content="", done=False)
        else:
            self.logger.warning(
                "Got a unexpected websocket msg_type",
                websocket_payload=response_data,
            )
            return WebSocketMessageOutput(content="", done=False)


@dataclass
class JupyterConfig:
    """Configurations for talking to JupyterHub and spawning a JupyterLab
    session.
    """

    image_selector: JupyterImageSelector
    """Method for selecting the JupyterLab image."""

    url_prefix: str = "/nb/"
    """URL path prefix for the JupyterHub service."""

    image_reference: str | None = None
    """Docker reference to the JupyterLab image to spawn.

    May be null if ``image_selector`` is is not
    `JupyterImageSelector.reference`.
    """

    image_size: str = "Large"
    """Size of the image to spawn (must be one of the sizes permitted by
    nublado2).
    """


class JupyterError(Exception):
    """An error related to Jupyter client usage."""

    @classmethod
    def from_response(
        cls, username: str, response: httpx.Response
    ) -> JupyterError:
        return cls(
            url=str(response.url),
            username=username,
            status=response.status_code,
            reason=response.reason_phrase,
            method=response.request.method,
            body=response.text,
        )

    @classmethod
    async def from_stream(
        cls, username: str, stream: httpx.Response
    ) -> JupyterError:
        body_bytes = await stream.aread()
        return cls(
            url=str(stream.url),
            username=username,
            status=stream.status_code,
            reason=stream.reason_phrase,
            method=stream.request.method,
            body=body_bytes.decode("utf-8"),
        )

    def __init__(
        self,
        *,
        url: str,
        username: str,
        status: int,
        reason: str | None,
        method: str,
        body: str | None = None,
    ) -> None:
        self.url = url
        self.status = status
        self.reason = reason
        self.method = method
        self.body = body
        self.username = username
        self.timestamp = datetime.datetime.now(tz=datetime.UTC)
        super().__init__(f"Status {status} from {method} {url}")

    def __str__(self) -> str:
        return (
            f"{self.username}: status {self.status} ({self.reason}) from"
            f" {self.method} {self.url}"
        )


class JupyterLabSessionError(Exception):
    """An error related to a JupyterLab websocket session."""

    def __init__(self, message: str, *, username: str) -> None:
        self.username = username
        super().__init__(message)

    @classmethod
    def from_exception(
        cls, *, username: str, exception: Exception
    ) -> JupyterLabSessionError:
        return cls(str(exception), username=username)


class CodeExecutionError(Exception):
    """An error related to code execution in a JupyterLab session."""

    def __init__(
        self,
        *,
        username: str,
        code: str,
        code_type: str = "code",
        error: str | None = None,
        status: str | None = None,
        result: str | None = None,
    ) -> None:
        self.username = username
        self.code = code
        self.code_type = code_type
        self.error = error
        self.status = status
        self.result = result
        super().__init__("Code execution failed")

    def __str__(self) -> str:
        message = (
            f"{self.username}: running {self.code_type} "
            f"'{self.code}' failed"
        )

        message += f"\nError: {self.error}"

        if self.result:
            message = f"{self.result}\n{message}"

        return message


class NotebookExecutionErrorModel(BaseModel):
    """The error from the ``/user/:username/rubin/execute`` endpoint."""

    traceback: Annotated[str, Field(description="The exeception traceback.")]

    ename: Annotated[str, Field(description="The exception name.")]

    evalue: Annotated[str, Field(description="The exception value.")]

    err_msg: Annotated[str, Field(description="The exception message.")]


class NotebookExecutionResult(BaseModel):
    """The result of the /user/:username/rubin/execute endpoint."""

    notebook: Annotated[
        str,
        Field(description="The notebook that was executed, as a JSON string."),
    ]

    resources: Annotated[
        dict[str, Any],
        Field(
            description=(
                "The resources used to execute the notebook, as a JSON string."
            )
        ),
    ]

    error: Annotated[
        NotebookExecutionErrorModel | None,
        Field(description="The error that occurred during execution."),
    ] = None


class JupyterClient:
    """A client for JupyterLab, via JupyterHub.

    This client can optionally be used as a async Python context manager.
    If not, remember to call the close() method to clean up the HTTP
    connections

    Parameters
    ----------
    user : `noteburst.jupyterclient.user.AuthenticatedUser`
        The user's information.
    logger : structlog.BoundLogger
        A logger instance that may be associated with existing context.
    config : JupyterConfig
        Configuration for the JupyterLab image to spawn.
    """

    def __init__(
        self,
        *,
        user: AuthenticatedUser,
        logger: BoundLogger,
        config: JupyterConfig,
    ) -> None:
        self.user = user
        self.logger = logger
        self.config = config

        self.jupyter_url = urljoin(
            str(noteburst_config.environment_url), self.config.url_prefix
        )

        self._headers = {
            "Authorization": f"Bearer {self.user.token}",
        }
        self.http_client = httpx.AsyncClient(
            headers=self._headers,
            follow_redirects=True,
            timeout=30,
        )
        self._lab_controller_client: LabControllerClient | None = None
        self._hub_xsrf: str | None = None
        self._lab_xsrf: str | None = None

    @property
    def lab_controller(self) -> LabControllerClient:
        if self._lab_controller_client:
            return self._lab_controller_client

        self._lab_controller_client = LabControllerClient(
            http_client=self.http_client,
            token=noteburst_config.gafaelfawr_token.get_secret_value(),
            url_prefix=noteburst_config.nublado_controller_path_prefix,
        )
        return self._lab_controller_client

    async def close(self) -> None:
        """Close the client."""
        self._lab_controller_client = None

        await self.http_client.aclose()

    def url_for(self, path: str) -> str:
        """Create a URL relative to the jupyter_url."""
        if self.jupyter_url.endswith("/"):
            return f"{self.jupyter_url}{path}"
        else:
            return f"{self.jupyter_url}/{path}"

    def url_for_websocket(self, path: str) -> str:
        """Create a wss:// URL relative to the jupyter_url."""
        http_url = self.url_for(path)
        return urlparse(http_url)._replace(scheme="wss").geturl()

    def _extract_xsrf(self, response: Response) -> str | None:
        """Extract the XSRF token from the cookies in a response.

        Parameters
        ----------
        response
            Response from a Jupyter server.

        Returns
        -------
        str or None
            Extracted XSRF value or `None` if none was present.
        """
        cookies = Cookies()
        cookies.extract_cookies(response)
        return cookies.get("_xsrf")

    async def log_into_hub(self) -> None:
        """Log into JupyterHub or raise a JupyterError."""
        self.logger.debug("Logging into JupyterHub")
        url = self.url_for("hub/home")
        r = await self.http_client.get(url, follow_redirects=False)
        while r.is_redirect:
            xsrf = self._extract_xsrf(r)
            if xsrf and xsrf != self._lab_xsrf:
                self._hub_xsrf = xsrf
            next_url = urljoin(url, r.headers["Location"])
            r = await self.http_client.get(next_url, follow_redirects=False)
        r.raise_for_status()
        xsrf = self._extract_xsrf(r)
        if xsrf and xsrf != self._lab_xsrf:
            self._hub_xsrf = xsrf

        if not self._hub_xsrf:
            raise JupyterError(
                reason="No XSRF token found for JupyterHub",
                url=url,
                username=self.user.username,
                status=r.status_code,
                method="GET",
                body=r.text,
            )
        self.logger.debug("Logged into JupyterHub with XSRF token")

    async def log_into_lab(self) -> None:
        """Log into JupyterLab or raise a JupyterError."""
        self.logger.debug("Logging into JupyterLab")
        url = self.url_for(f"user/{self.user.username}/lab")
        # Setting ``Sec-Fetch-Mode`` is not currently required, but it
        # suppresses an annoying error message in the lab logs.
        headers = {"Sec-Fetch-Mode": "navigate"}
        r = await self.http_client.get(
            url, headers=headers, follow_redirects=False
        )
        while r.is_redirect:
            xsrf = self._extract_xsrf(r)
            if xsrf and xsrf != self._hub_xsrf:
                self._lab_xsrf = xsrf
            next_url = urljoin(url, r.headers["Location"])
            r = await self.http_client.get(
                next_url, headers=headers, follow_redirects=False
            )
        r.raise_for_status()
        xsrf = self._extract_xsrf(r)
        if xsrf and xsrf != self._hub_xsrf:
            self._lab_xsrf = xsrf
        if not self._lab_xsrf:
            raise JupyterError(
                reason="No XSRF token found for JupyterLab",
                url=url,
                username=self.user.username,
                status=r.status_code,
                method="GET",
                body=r.text,
            )
        self.logger.debug("Logged into JupyterLab with XSRF token")

    async def spawn_lab(self) -> JupyterImage:
        """Spawn a JupyterLab pod."""
        spawn_url = self.url_for("hub/spawn")

        # Retrieving the spawn page before POSTing to it appears to trigger
        # some necessary internal state construction (and also more accurately
        # simulates a user interaction).  See DM-23864.
        headers = dict(self._headers)
        if self._hub_xsrf:
            headers["X-XSRFToken"] = self._hub_xsrf
        _ = await self.http_client.get(spawn_url, headers=headers)

        # POST the options form to the spawn page.  This should redirect to
        # the spawn-pending page, which will return a 200.
        image = await self._get_spawn_image()
        data = self._build_jupyter_spawn_form(image)
        r = await self.http_client.post(spawn_url, data=data, headers=headers)
        if r.status_code != 200:
            raise JupyterError.from_response(self.user.username, r)

        # Return information about the image spawned so that we can use it to
        # annotate timers and get it into error reports.
        return image

    async def spawn_progress(self) -> AsyncIterator[SpawnProgressMessage]:
        """Monitor lab spawn progress.

        This is an EventStream API, which provides a stream of events until
        the lab is spawned or the spawn fails.
        """
        progress_url = self.url_for(
            f"hub/api/users/{self.user.username}/server/progress"
        )
        referer_url = self.url_for("hub/home")
        headers = {"Referer": referer_url}
        if self._hub_xsrf:
            headers["X-XSRFToken"] = self._hub_xsrf
        while True:
            async with self.http_client.stream(
                "GET", progress_url, headers=headers
            ) as response_stream:
                if response_stream.status_code != 200:
                    raise await JupyterError.from_stream(
                        self.user.username, response_stream
                    )
                progress = JupyterSpawnProgress(response_stream, self.logger)
                async for message in progress:
                    yield message

                # Sometimes we get only the initial request message and then
                # the progress API immediately closes the connection.  If that
                # happens, try reconnecting to the progress stream after a
                # short delay.
                if message.progress > 0:
                    break
                await asyncio.sleep(1)
                self.logger.info("Retrying spawn progress request")

    async def _get_spawn_image(self) -> JupyterImage:
        """Determine what image to spawn."""
        if self.config.image_selector == JupyterImageSelector.recommended:
            image = await self.lab_controller.get_recommended()
        elif self.config.image_selector == JupyterImageSelector.weekly:
            image = await self.lab_controller.get_latest_weekly()
        elif self.config.image_selector == JupyterImageSelector.reference:
            if self.config.image_reference is None:
                raise ValueError(
                    "No image reference provided using "
                    "JupyterImageSelector.reference."
                )
            image = await self.lab_controller.get_by_reference(
                self.config.image_reference
            )
        else:
            # This should be prevented by the model as long as we don't add a
            # new image class without adding the corresponding condition.
            raise ValueError(
                f"Invalid image_selector {self.config.image_selector}"
            )
        return image

    def _build_jupyter_spawn_form(self, image: JupyterImage) -> dict[str, Any]:
        """Construct the form to submit to the JupyterHub spawning page."""
        return {
            "image_list": [image.reference],
            "image_dropdown": [image.reference],
            "size": self.config.image_size,
        }

    async def stop_lab(self) -> None:
        """Stop the JupyterLab server."""
        if await self.is_lab_stopped():
            self.logger.info("Lab is already stopped")
            return
        user = self.user.username
        server_url = self.url_for(f"hub/api/users/{user}/server")
        referer_url = self.url_for("hub/home")
        headers = {"Referer": referer_url}
        if self._hub_xsrf:
            headers["X-XSRFToken"] = self._hub_xsrf
        r = await self.http_client.delete(server_url, headers=headers)
        if r.status_code not in [200, 202, 204]:
            raise JupyterError.from_response(self.user.username, r)

    async def is_lab_stopped(self, *, final: bool = False) -> bool:
        """Determine if the lab is fully stopped.

        Parameters
        ----------
        final : `bool`
            The last attempt, so log some additional information if the lab
            still isn't gone.
        """
        user_url = self.url_for(f"hub/api/users/{self.user.username}")
        referer_url = self.url_for("hub/home")
        headers = {"Referer": referer_url}
        if self._hub_xsrf:
            headers["X-XSRFToken"] = self._hub_xsrf
        r = await self.http_client.get(user_url, headers=headers)
        if r.status_code != 200:
            raise JupyterError.from_response(self.user.username, r)
        data = r.json()
        result = data["servers"] == {}
        if final and not result:
            msg = f'Server data still shows running lab: {data["servers"]}'
            self.logger.warning(msg)
        return result

    @contextlib.asynccontextmanager
    async def open_lab_session(
        self, notebook_name: str | None = None, *, kernel_name: str = "LSST"
    ) -> AsyncGenerator[JupyterLabSession, None]:
        """Open a JupyterLab session.

        Send and receive messages from JupyterLab using the ``websocket``
        property on `JupyterLabSession`.
        """
        self.logger.debug("Opening JupyterLab session")
        session_url = self.url_for(f"user/{self.user.username}/api/sessions")
        session_type = "notebook" if notebook_name else "console"
        body = {
            "kernel": {"name": kernel_name},
            "name": notebook_name or "(no notebook)",
            "path": notebook_name if notebook_name else uuid4().hex,
            "type": session_type,
        }
        headers = {}
        if self._lab_xsrf:
            headers["X-XSRFToken"] = self._lab_xsrf
        else:
            self.logger.warning("No XSRF token found for JupyterLab.")
        r = await self.http_client.post(
            session_url, json=body, headers=headers
        )
        if r.status_code != 201:
            raise JupyterError.from_response(self.user.username, r)
        session_resource = r.json()

        kernel_id = session_resource["kernel"]["id"]
        http_channels_uri = self.url_for(
            f"user/{self.user.username}/api/kernels/{kernel_id}/channels"
        )
        wss_channels_uri = self.url_for_websocket(
            f"user/{self.user.username}/api/kernels/{kernel_id}/channels"
        )

        # Generate a mock request and copy its headers / cookies over to the
        # websocket connection.
        mock_request = self.http_client.build_request("GET", http_channels_uri)
        headers = {
            h: mock_request.headers[h] for h in ("authorization", "cookie")
        }
        if self._lab_xsrf:
            headers["X-XSRFToken"] = self._lab_xsrf

        session_id: str | None = None  # will be set if a session is opened
        self.logger.debug("Trying to create websocket connection")
        try:
            # An alternative to the async context it to use connect in an
            # infinite async generator that can automatically reconnect
            # if the connection is dropped. This could be good for very
            # long lived clients
            # https://websockets.readthedocs.io/en/stable/reference/client.html#using-a-connection
            async with websockets.connect(
                wss_channels_uri, extra_headers=headers
            ) as websocket:
                self.logger.info("Created websocket connection")
                jupyter_lab_session = JupyterLabSession(
                    username=self.user.username,
                    session_id=session_resource["id"],
                    kernel_id=kernel_id,
                    websocket=websocket,
                    logger=self.logger,
                )
                session_id = jupyter_lab_session.session_id
                yield jupyter_lab_session
        except WebSocketException as e:
            raise JupyterLabSessionError.from_exception(
                username=self.user.username, exception=e
            ) from e
        finally:
            if session_id:
                session_id_url = self.url_for(
                    f"user/{self.user.username}/api/sessions/{session_id}"
                )
                r = await self.http_client.delete(
                    session_id_url, headers=headers
                )
                if r.status_code != 204:
                    raise JupyterError.from_response(self.user.username, r)

    async def execute_notebook(
        self, notebook: dict[str, Any], kernel_name: str = "LSST"
    ) -> NotebookExecutionResult:
        """Execute a Jupyter notebook through the JupyterLab Notebook execution
        extension.

        Parameters
        ----------
        notebook : dict
            A Jupyter Notebook, parsed from its JSON form.

        Returns
        -------
        notebook : dict
            The executed Jupyter Notebook.

        Raises
        ------
        NotebookExecutionResult
            Raised if there is an error interacting with the JupyterLab
            Notebook execution extension.
        """
        exec_url = self.url_for(f"user/{self.user.username}/rubin/execution")
        headers = {}
        if self._lab_xsrf:
            headers["X-XSRFToken"] = self._lab_xsrf
        elif self._hub_xsrf:
            self.logger.warning(
                "No XSRF token found for JupyterLab, using hub token."
            )
            headers["X-XSRFToken"] = self._hub_xsrf
        try:
            # The timeout is designed to catch issues connecting to JupyterLab
            # but to wait as long as possible for the notebook itself
            # to execute.
            r = await self.http_client.post(
                exec_url,
                content=json.dumps(notebook).encode("utf-8"),
                headers=headers,
                timeout=Timeout(5.0, read=None),
            )
            r.raise_for_status()
        except httpx.ReadTimeout as e:
            raise JupyterError(
                url=exec_url,
                username=self.user.username,
                status=500,
                reason="/execution endpoint timeout",
                method="POST",
                body=str(e),
            ) from e
        except httpx.HTTPStatusError as e:
            # This often occurs from timeouts, so we want to convert the
            # generic HTTPError to a JupyterError.
            raise JupyterError(
                url=exec_url,
                username=self.user.username,
                status=r.status_code,
                reason="Internal Server Error",
                method="POST",
                body=str(e),
            ) from e
        if r.status_code != 200:
            raise JupyterError.from_response(self.user.username, r)
        self.logger.debug("Got response from /rubin/execution", text=r.text)

        return NotebookExecutionResult.model_validate_json(r.text)

    async def get_jupyterlab_env(self) -> dict[str, Any]:
        """Get metadata from the JupyterLab environment endpoint.

        Uses the ``/user/:username/rubin/environment`` extension endpoint.
        """
        environment_url = self.url_for(
            f"user/{self.user.username}/rubin/environment"
        )
        headers = {}
        if self._lab_xsrf:
            headers["X-XSRFToken"] = self._lab_xsrf
        r = await self.http_client.get(environment_url, headers=headers)
        if r.status_code != 200:
            raise JupyterError.from_response(self.user.username, r)
        return r.json()
