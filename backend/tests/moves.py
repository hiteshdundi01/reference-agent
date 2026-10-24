"""Moves the tests make on a request, as a person or the agent makes them."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import update

from backend.database import engine, requests

SECTION = "Section 3"
REASON = "The goods arrived damaged, which Section 3 covers in full."


def start(caller: TestClient, request_id: str) -> dict:
    response = caller.post(f"/api/requests/{request_id}/start")
    assert response.status_code == 200, response.text
    return response.json()


def decision(attempt=1, revision=1, kind="approve", amount=45.0, **changes) -> dict:
    """A decision body as the agent's tool sends it."""
    body = {
        "attempt": attempt,
        "revision": revision,
        "decision": kind,
        "section": SECTION,
        "reason": REASON,
        "decided_by": "agent (stub model)",
    }
    if kind == "approve":
        body["amount"] = amount
    return body | changes


def decide(agent: TestClient, request_id: str, **given):
    return agent.post(f"/api/requests/{request_id}/decision", json=decision(**given))


def held(
    rep: TestClient, agent: TestClient, request_id="REQ-1003", amount=320.0
) -> int:
    """Start a request and have the agent approve it over the limit; return the
    held decision's id."""
    start(rep, request_id)
    response = decide(agent, request_id, amount=amount)
    assert response.json()["state"] == "held", response.text
    return response.json()["decision_id"]


def go_quiet(request_id: str, minutes: int = 6) -> None:
    """Make the agent's last word on a request this many minutes old."""
    with engine().begin() as connection:
        connection.execute(
            update(requests)
            .where(requests.c.id == request_id)
            .values(heard_at=datetime.now(UTC) - timedelta(minutes=minutes))
        )
