"""Running the backend and the agent's app on ports of their own, and transports
that fail on cue, for the end-to-end tests."""

import socket
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import httpx
import uvicorn


def free_port() -> int:
    with socket.socket() as finder:
        finder.bind(("127.0.0.1", 0))
        return finder.getsockname()[1]


@contextmanager
def serving(app: Any, port: int) -> Iterator[str]:
    """Serve an app on a loopback port for the block, and return its address."""
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        threading.Event().wait(0.01)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(5)


class FailingOnCue(httpx.BaseTransport):
    """A transport that sends requests on, except where a rule says what goes
    wrong: "lost" sends the request but loses its answer, "timeout" times out
    before sending, and "down" finds nothing listening."""

    def __init__(self) -> None:
        self.rule: Callable[[httpx.Request], str | None] = lambda _: None
        self.inner = httpx.HTTPTransport()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        what = self.rule(request)
        if what == "down":
            raise httpx.ConnectError("nothing is listening", request=request)
        if what == "timeout":
            raise httpx.ReadTimeout("no answer in time", request=request)
        response = self.inner.handle_request(request)
        if what == "lost":
            response.read()
            raise httpx.ReadTimeout("the answer was lost", request=request)
        return response


def once(
    matches: Callable[[httpx.Request], bool], what: str
) -> Callable[[httpx.Request], str | None]:
    """A rule that makes the first matching request go wrong as given."""
    done: list[bool] = []

    def rule(request: httpx.Request) -> str | None:
        if not done and matches(request):
            done.append(True)
            return what
        return None

    return rule
