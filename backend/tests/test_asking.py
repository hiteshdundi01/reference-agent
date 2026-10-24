"""Phase 2: asking the agent. A move is undone when the agent definitely didn't
start, and kept when the outcome is unknown."""

import httpx
import pytest

from backend import requests as refund_requests
from backend.database import engine
from backend.tests.moves import go_quiet, held, start

NOT_STARTED = [
    (httpx.ConnectError("refused"), 503, "The agent isn't running"),
    (httpx.ConnectTimeout("slow"), 503, "The agent isn't running"),
    (httpx.Response(409, json={"detail": "busy"}), 502, "couldn't take the work"),
    (httpx.Response(200, json={"refused": "already working"}), 409, "already working"),
]
# A timeout, a cut-off answer or a success that isn't one of the agent's answers.
UNKNOWN = [
    httpx.ReadTimeout("no answer"),
    httpx.RemoteProtocolError("cut off"),
    httpx.Response(200, json={"something": "else"}),
    httpx.Response(200, text="not json"),
]


def answering(outcome):
    def handler(request: httpx.Request) -> httpx.Response:
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return handler


def test_the_agent_is_asked_with_its_key(rep, agent_answers):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"accepted": True})

    agent_answers(handler)
    start(rep, "REQ-1001")
    assert seen[0].url == "http://127.0.0.1:8080/invocations"
    assert seen[0].headers["Authorization"].startswith("Bearer test-agent-key")


@pytest.mark.parametrize(("outcome", "status", "words"), NOT_STARTED)
def test_a_start_the_agent_didnt_take_is_undone(
    rep, agent_answers, outcome, status, words
):
    agent_answers(answering(outcome))
    response = rep.post("/api/requests/REQ-1001/start")
    assert response.status_code == status
    assert words in response.json()["detail"]
    request = rep.get("/api/requests/REQ-1001").json()
    assert (request["state"], request["attempt"]) == ("waiting", 0)
    assert rep.get("/api/requests/REQ-1001/steps").json() == []


@pytest.mark.parametrize("outcome", UNKNOWN)
def test_a_start_with_an_unknown_outcome_is_kept(rep, agent_answers, outcome):
    agent_answers(answering(outcome))
    response = rep.post("/api/requests/REQ-1001/start")
    assert response.status_code == 503
    assert "reload" in response.json()["detail"]
    request = rep.get("/api/requests/REQ-1001").json()
    assert (request["state"], request["attempt"]) == ("working", 1)


def test_a_send_back_the_agent_didnt_take_is_undone(
    rep, agent, supervisor, agent_answers
):
    decision_id = held(rep, agent)
    agent_answers(answering(httpx.ConnectError("refused")))
    response = supervisor.post(
        "/api/requests/REQ-1003/send-back",
        json={"decision_id": decision_id, "note": "Look again."},
    )
    assert response.status_code == 503
    request = rep.get("/api/requests/REQ-1003").json()
    assert (request["state"], request["revision"], request["send_back"]) == (
        "held",
        1,
        None,
    )
    assert request["decision"]["id"] == decision_id
    kinds = [step["kind"] for step in rep.get("/api/requests/REQ-1003/steps").json()]
    assert "sent_back" not in kinds


def test_a_send_back_with_an_unknown_outcome_is_kept(
    rep, agent, supervisor, agent_answers
):
    decision_id = held(rep, agent)
    agent_answers(answering(httpx.ReadTimeout("no answer")))
    response = supervisor.post(
        "/api/requests/REQ-1003/send-back",
        json={"decision_id": decision_id, "note": "Look again."},
    )
    assert response.status_code == 503
    request = rep.get("/api/requests/REQ-1003").json()
    assert (request["state"], request["revision"]) == ("working", 2)
    assert request["send_back"]["note"] == "Look again."


def test_a_sign_off_stands_when_the_agent_cant_be_reached(
    rep, agent, supervisor, agent_answers
):
    decision_id = held(rep, agent)
    agent_answers(answering(httpx.ConnectError("refused")))
    response = supervisor.post(
        "/api/requests/REQ-1003/sign-off", json={"decision_id": decision_id}
    )
    assert response.status_code == 200
    assert response.json()["state"] == "refunded"
    assert response.json()["refund"]["signed_off_by"] == "morgan.diaz@acme.example"


def heard_from_the_agent_then(outcome, request_id, attempt=1):
    """An agent that records a step on the request, then answers as given."""

    def handler(request: httpx.Request) -> httpx.Response:
        with engine().begin() as connection:
            refund_requests.add_step(
                connection, request_id, attempt, "reply", "Working"
            )
        return answering(outcome)(request)

    return handler


def test_a_takeover_isnt_undone_once_the_agent_has_been_heard_from(rep, agent_answers):
    start(rep, "REQ-1001")
    go_quiet("REQ-1001")
    refusal = httpx.Response(200, json={"refused": "already working"})
    agent_answers(heard_from_the_agent_then(refusal, "REQ-1001"))
    assert rep.post("/api/requests/REQ-1001/start").status_code == 409
    request = rep.get("/api/requests/REQ-1001").json()
    assert (request["state"], request["attempt"]) == ("working", 1)
    kinds = [step["kind"] for step in rep.get("/api/requests/REQ-1001/steps").json()]
    assert kinds == ["started", "started", "reply"]


def test_a_send_back_isnt_undone_once_the_agent_has_been_heard_from(
    rep, agent, supervisor, agent_answers
):
    decision_id = held(rep, agent)
    refusal = httpx.Response(200, json={"refused": "already working"})
    agent_answers(heard_from_the_agent_then(refusal, "REQ-1003"))
    response = supervisor.post(
        "/api/requests/REQ-1003/send-back",
        json={"decision_id": decision_id, "note": "Look again."},
    )
    assert response.status_code == 409
    request = rep.get("/api/requests/REQ-1003").json()
    assert (request["state"], request["revision"]) == ("working", 2)
    assert request["send_back"]["note"] == "Look again."
