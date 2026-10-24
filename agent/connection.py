"""The one connection to the backend: its address, the one HTTP client and the
agent's key, and how a request is sent and refused."""

import os
from typing import Any

import httpx

APP_API = "APP_API"
DEFAULT_URL = "http://127.0.0.1:8000"
API_KEY_HEADER = "X-API-Key"
MISSING_KEY = "AGENT_KEY is missing. Add it to .env"

# Retries a refused connection a few times, while the backend starts.
backend = httpx.Client(
    base_url=f"{os.getenv(APP_API, DEFAULT_URL)}/api",
    timeout=30,
    transport=httpx.HTTPTransport(retries=3),
)


class Refused(Exception):
    """The backend refused a request, with its status code and reason."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"{status_code}: {detail}")
        self.status_code, self.detail = status_code, detail


def agent_key() -> str:
    """The agent's key, read as each request is sent."""
    key = os.getenv("AGENT_KEY")
    if not key:
        raise RuntimeError(MISSING_KEY)
    return key


def call(method: str, path: str, **request: Any) -> Any:
    """Send one request to the backend with the agent's key and return its JSON,
    or raise Refused."""
    response = backend.request(
        method, path, headers={API_KEY_HEADER: agent_key()}, **request
    )
    if response.is_error:
        raise Refused(response.status_code, response.json()["detail"])
    return response.json()
