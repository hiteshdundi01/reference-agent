"""Phase 4: the real backend and the real agent's app on ports of their own, the
stub model, and checkpoints in a file, through every way the work can go."""

import json
import os
import time

import httpx
import pytest
from sqlalchemy import select

from agent import connection, models
from agent.entrypoint import app as agent_app
from agent.tests.servers import FailingOnCue, free_port, once, serving
from agent.tests.stubs import approve, escalate, reads, stub
from backend import agent_service
from backend.database import engine, refunds
from backend.main import app as backend_app
from backend.tests.moves import decision, go_quiet


class ProcessDied(BaseException):
    """The agent's process stopping mid-run, which nothing in it can catch."""


@pytest.fixture
def scripts(monkeypatch):
    """The stub models the agent's app gets, one for each piece of work, in turn."""
    queue: list = []
    monkeypatch.setattr(models, "chat_model", lambda: stub(*queue.pop(0)))
    return queue


@pytest.fixture
def agent_side():
    """The agent's way to the backend, which a test can make fail on cue."""
    return FailingOnCue()


@pytest.fixture
def backend_side():
    """The backend's way to the agent, which a test can make fail on cue."""
    return FailingOnCue()


@pytest.fixture(autouse=True)
def running(monkeypatch, agent_side, backend_side):
    """Both apps on loopback ports, each reaching the other over HTTP."""
    with (
        serving(backend_app, free_port()) as backend_url,
        serving(agent_app, free_port()) as agent_url,
    ):
        monkeypatch.setenv("AGENT_URL", agent_url)
        monkeypatch.setattr(
            agent_service, "client", httpx.Client(timeout=10, transport=backend_side)
        )
        monkeypatch.setattr(
            connection,
            "backend",
            httpx.Client(
                base_url=f"{backend_url}/api", timeout=10, transport=agent_side
            ),
        )
        yield agent_url


def settled(rep, request_id: str, state: str) -> dict:
    """Wait until the agent is idle and the request is in the state."""
    request: dict = {}
    for _ in range(200):
        busy = httpx.get(f"{os.environ['AGENT_URL']}/ping").json()["status"]
        request = rep.get(f"/api/requests/{request_id}").json()
        if busy == "Healthy" and request["state"] == state:
            return request
        time.sleep(0.02)
    raise AssertionError(f"{request_id} is {request['state']}, not {state}")


def refunds_of(request_id: str) -> int:
    with engine().connect() as c:
        return len(
            list(c.execute(select(refunds).where(refunds.c.request_id == request_id)))
        )


def is_decision(request: httpx.Request) -> bool:
    return request.method == "POST" and request.url.path.endswith("/decision")


def is_resume(request: httpx.Request) -> bool:
    return json.loads(request.content or b"{}").get("operation") == "resume"


def held(rep, scripts, request_id="REQ-1003") -> int:
    scripts.append([approve(320.0)])
    rep.post(f"/api/requests/{request_id}/start")
    return settled(rep, request_id, "held")["decision"]["id"]


def test_1_an_approval_within_the_limit_is_refunded_once(rep, scripts):
    scripts.append([*reads("read_request", "read_order"), approve(45.0)])
    assert rep.post("/api/requests/REQ-1001/start").status_code == 200
    settled(rep, "REQ-1001", "refunded")
    assert refunds_of("REQ-1001") == 1


def test_2_a_sign_off_refunds_and_ends_the_graph(rep, supervisor, scripts):
    decision_id = held(rep, scripts)
    scripts.append([])
    supervisor.post(
        "/api/requests/REQ-1003/sign-off", json={"decision_id": decision_id}
    )
    request = settled(rep, "REQ-1003", "refunded")
    assert request["refund"]["signed_off_by"] == "morgan.diaz@acme.example"
    assert refunds_of("REQ-1003") == 1
    assert scripts == []


def test_3_a_send_back_gets_a_changed_decision_once(rep, supervisor, agent, scripts):
    decision_id = held(rep, scripts)
    scripts.append([escalate(section="Section 3", reason="The photo needs a person.")])
    supervisor.post(
        "/api/requests/REQ-1003/send-back",
        json={"decision_id": decision_id, "note": "The photo shows a scratch."},
    )
    request = settled(rep, "REQ-1003", "escalated")
    assert request["revision"] == 2
    replay = decision(
        revision=2,
        kind="escalate",
        section="Section 3",
        reason="The photo needs a person.",
    )
    assert agent.post("/api/requests/REQ-1003/decision", json=replay).status_code == 200
    # The held approval, sent again, gets what it did then; a different decision
    # for that old revision is refused.
    again = agent.post("/api/requests/REQ-1003/decision", json=decision(amount=320.0))
    assert (again.status_code, again.json()["state"]) == (200, "held")
    other = agent.post("/api/requests/REQ-1003/decision", json=decision(kind="decline"))
    assert other.status_code == 409
    kinds = [s["kind"] for s in rep.get("/api/requests/REQ-1003/steps").json()]
    assert kinds.count("decision") == 2
    assert "sent_back" in kinds


def test_4_a_lost_answer_to_a_decision_is_retried_and_refunds_once(
    rep, scripts, agent_side
):
    agent_side.rule = once(is_decision, "lost")
    scripts.append([approve(45.0)])
    rep.post("/api/requests/REQ-1001/start")
    settled(rep, "REQ-1001", "refunded")
    assert refunds_of("REQ-1001") == 1
    # The decision was sent twice: once with its answer lost, then retried.
    steps = rep.get("/api/requests/REQ-1001/steps").json()
    approvals = [step for step in steps if step["text"].startswith("approve_refund(")]
    assert len(approvals) == 2


@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
def test_5_after_a_crash_a_stalled_request_carries_on(rep, scripts):
    scripts.append([*reads("read_request", "read_order"), ProcessDied()])
    rep.post("/api/requests/REQ-1001/start")
    settled(rep, "REQ-1001", "working")
    go_quiet("REQ-1001")
    model_steps = len(rep.get("/api/requests/REQ-1001/steps").json())
    scripts.append([approve(45.0)])
    taken = rep.post("/api/requests/REQ-1001/start").json()
    assert taken["attempt"] == 1
    settled(rep, "REQ-1001", "refunded")
    assert refunds_of("REQ-1001") == 1
    assert model_steps > 1


def test_6_a_send_back_that_never_reached_the_agent_is_recovered(
    rep, supervisor, scripts, backend_side
):
    decision_id = held(rep, scripts)
    backend_side.rule = once(is_resume, "timeout")
    response = supervisor.post(
        "/api/requests/REQ-1003/send-back",
        json={"decision_id": decision_id, "note": "Check the photo date."},
    )
    assert response.status_code == 503
    settled(rep, "REQ-1003", "working")
    go_quiet("REQ-1003")
    scripts.append([escalate(section="Section 3")])
    rep.post("/api/requests/REQ-1003/start")
    request = settled(rep, "REQ-1003", "escalated")
    assert request["revision"] == 2


def test_7_a_send_back_with_the_agent_down_goes_back_to_held(
    rep, supervisor, scripts, backend_side
):
    decision_id = held(rep, scripts)
    backend_side.rule = once(is_resume, "down")
    response = supervisor.post(
        "/api/requests/REQ-1003/send-back",
        json={"decision_id": decision_id, "note": "Check the photo date."},
    )
    assert response.status_code == 503
    request = rep.get("/api/requests/REQ-1003").json()
    assert (request["state"], request["revision"], request["send_back"]) == (
        "held",
        1,
        None,
    )


def test_8_a_sign_off_with_the_agent_down_refunds_once(
    rep, supervisor, scripts, backend_side
):
    decision_id = held(rep, scripts)
    backend_side.rule = once(is_resume, "down")
    response = supervisor.post(
        "/api/requests/REQ-1003/sign-off", json={"decision_id": decision_id}
    )
    assert response.json()["state"] == "refunded"
    assert refunds_of("REQ-1003") == 1
