"""The one way the backend reaches the agent: asking it to work or resume a
request, at AGENT_URL with the agent's key.

Each ask ends in one of three outcomes. Accepted. Definitely not started: the
agent was never reached, or it refused or answered with an error. Unknown: the
request was sent, but no answer came back in time."""

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

AGENT_URL = "AGENT_URL"
DEFAULT_URL = "http://127.0.0.1:8080"
INVOCATIONS = "/invocations"
ACCEPTED = {"accepted": True}
MAY_HAVE_STARTED = "The agent may have started; reload in a minute"

# A connection that can't be made in 2 seconds was never made; an answer that
# takes longer than 10 is an unknown outcome.
client = httpx.Client(timeout=httpx.Timeout(10, connect=2))


class Outcome(Enum):
    ACCEPTED = "accepted"
    NOT_STARTED = "not started"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Asked:
    outcome: Outcome
    status_code: int = 200
    reason: str = ""


def ask(payload: dict[str, Any]) -> Asked:
    """Send one payload to the agent's /invocations and say how it went."""
    url = os.getenv(AGENT_URL, DEFAULT_URL) + INVOCATIONS
    headers = {"Authorization": f"Bearer {os.getenv('AGENT_KEY', '')}"}
    try:
        response = client.post(url, json=payload, headers=headers)
    except (httpx.ConnectError, httpx.ConnectTimeout):
        return Asked(Outcome.NOT_STARTED, 503, "The agent isn't running")
    except httpx.TransportError:
        return Asked(Outcome.UNKNOWN, 503, MAY_HAVE_STARTED)
    return answer_of(response)


def answer_of(response: httpx.Response) -> Asked:
    if response.is_error:
        return Asked(
            Outcome.NOT_STARTED,
            502,
            f"The agent couldn't take the work: {response.text}",
        )
    try:
        body = response.json()
    except ValueError:
        body = response.text
    if body == ACCEPTED:
        return Asked(Outcome.ACCEPTED)
    if isinstance(body, dict) and "refused" in body:
        return Asked(Outcome.NOT_STARTED, 409, f"The agent refused: {body['refused']}")
    # A success that isn't one of the agent's answers doesn't show the work never
    # began, so the move is kept.
    return Asked(Outcome.UNKNOWN, 503, MAY_HAVE_STARTED)


def work(request_id: str) -> Asked:
    return ask({"operation": "work", "request_id": request_id})


def resume(request_id: str, answer: dict[str, Any]) -> Asked:
    return ask({"operation": "resume", "request_id": request_id, "answer": answer})
