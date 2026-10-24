"""Phase 4: the agent's app takes one operation at a time per request, and a
failure ends the attempt with its reason."""

import threading
import time

import pytest
from fastapi.testclient import TestClient

from agent import entrypoint, harness, models
from agent.tests.stubs import stub
from backend.tests.credentials import TEST_KEY
from backend.tests.moves import start

KEY = {"Authorization": f"Bearer {TEST_KEY}"}


@pytest.fixture
def app():
    with TestClient(entrypoint.app) as client:
        yield client


@pytest.fixture
def held_work(monkeypatch):
    """Work that waits until the test lets it go."""
    release = threading.Event()
    monkeypatch.setattr(harness, "work", lambda *_: release.wait(5))
    monkeypatch.setattr(models, "chat_model", stub)
    yield release
    release.set()


def until_idle(app):
    for _ in range(100):
        if app.get("/ping").json()["status"] == "Healthy":
            return
        time.sleep(0.05)
    raise AssertionError("the agent stayed busy")


def test_the_health_check_needs_no_key(app):
    response = app.post("/invocations", json={"operation": "health"})
    assert response.json() == {"healthy": True}


def test_work_needs_the_agents_key(app):
    payload = {"operation": "work", "request_id": "REQ-1001"}
    assert app.post("/invocations", json=payload).status_code == 401
    wrong = {"Authorization": "Bearer wrong"}
    assert app.post("/invocations", json=payload, headers=wrong).status_code == 401


@pytest.mark.parametrize(
    ("payload", "words"),
    [
        ({"operation": "launch_rockets"}, "operation: must be one of"),
        ({"operation": "work"}, "request_id"),
        ({"operation": "work", "request_id": "REQ-1001", "extra": "x"}, "extra"),
        (
            {"operation": "resume", "request_id": "REQ-1", "answer": {"kind": "maybe"}},
            "kind",
        ),
        ("not an object", "the payload"),
    ],
)
def test_a_payload_it_cant_read_gets_a_400_that_says_why(app, payload, words):
    response = app.post("/invocations", json=payload, headers=KEY)
    assert response.status_code == 400
    assert words in response.json()["detail"]
    assert "launch_rockets" not in response.json()["detail"]


def test_work_is_taken_at_once_and_runs_on_a_thread(app, held_work):
    payload = {"operation": "work", "request_id": "REQ-1001"}
    assert app.post("/invocations", json=payload, headers=KEY).json() == {
        "accepted": True
    }
    assert app.get("/ping").json() == {"status": "HealthyBusy"}
    held_work.set()
    until_idle(app)


def test_a_second_piece_of_work_on_the_same_request_is_refused(app, held_work):
    payload = {"operation": "work", "request_id": "REQ-1001"}
    app.post("/invocations", json=payload, headers=KEY)
    again = app.post("/invocations", json=payload, headers=KEY).json()
    assert again == {"refused": "Request REQ-1001 is already being worked"}
    other = {"operation": "work", "request_id": "REQ-1002"}
    assert app.post("/invocations", json=other, headers=KEY).json() == {
        "accepted": True
    }
    held_work.set()
    until_idle(app)


def test_an_unhandled_error_fails_the_attempt_with_its_reason(app, rep, monkeypatch):
    start(rep, "REQ-1001")

    def broken(*_):
        raise RuntimeError("the model provider is down")

    monkeypatch.setattr(harness, "work", broken)
    monkeypatch.setattr(models, "chat_model", stub)
    app.post(
        "/invocations",
        json={"operation": "work", "request_id": "REQ-1001"},
        headers=KEY,
    )
    until_idle(app)
    request = rep.get("/api/requests/REQ-1001").json()
    assert request["state"] == "failed"
    assert request["failure"] == "RuntimeError: the model provider is down"


def test_a_failure_on_a_finished_request_leaves_it_as_it_is(
    app, rep, agent, monkeypatch
):
    start(rep, "REQ-1001")
    agent.post(
        "/api/requests/REQ-1001/decision",
        json={
            "attempt": 1,
            "revision": 1,
            "decision": "escalate",
            "section": "Section 6",
            "reason": "A person should look.",
            "decided_by": "agent (stub)",
        },
    )

    def broken(*_):
        raise RuntimeError("late")

    monkeypatch.setattr(harness, "work", broken)
    monkeypatch.setattr(models, "chat_model", stub)
    app.post(
        "/invocations",
        json={"operation": "work", "request_id": "REQ-1001"},
        headers=KEY,
    )
    until_idle(app)
    assert rep.get("/api/requests/REQ-1001").json()["state"] == "escalated"


def test_resume_hands_the_supervisors_answer_to_the_harness(app, monkeypatch):
    given = []
    monkeypatch.setattr(
        harness, "resume", lambda request_id, answer, *_: given.append(answer)
    )
    monkeypatch.setattr(models, "chat_model", stub)
    payload = {
        "operation": "resume",
        "request_id": "REQ-1003",
        "answer": {"kind": "sent_back", "note": "Look again.", "revision": 2},
    }
    assert app.post("/invocations", json=payload, headers=KEY).json() == {
        "accepted": True
    }
    until_idle(app)
    assert given == [{"kind": "sent_back", "note": "Look again.", "revision": 2}]


def test_a_key_without_its_scheme_is_refused(app):
    payload = {"operation": "work", "request_id": "REQ-1001"}
    bare = {"Authorization": TEST_KEY}
    assert app.post("/invocations", json=payload, headers=bare).status_code == 401


def test_a_stale_worker_never_fails_a_newer_attempt(app, rep, agent, monkeypatch):
    """A worker on attempt 1 fails only after a person has started attempt 2. Its
    failure names attempt 1, which the backend refuses, so attempt 2 goes on."""
    start(rep, "REQ-1001")
    has_read, late = threading.Event(), threading.Event()

    def fails_late(request, *_):
        has_read.set()
        late.wait(5)
        raise RuntimeError(f"attempt {request['attempt']} gave up")

    monkeypatch.setattr(harness, "work", fails_late)
    monkeypatch.setattr(models, "chat_model", stub)
    app.post(
        "/invocations",
        json={"operation": "work", "request_id": "REQ-1001"},
        headers=KEY,
    )
    assert has_read.wait(5)
    agent.post("/api/requests/REQ-1001/failure", json={"attempt": 1, "reason": "x"})
    start(rep, "REQ-1001")
    late.set()
    until_idle(app)
    request = rep.get("/api/requests/REQ-1001").json()
    assert (request["state"], request["attempt"]) == ("working", 2)
