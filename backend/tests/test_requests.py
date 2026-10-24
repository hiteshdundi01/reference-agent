"""Phase 2: every move in docs/PLAN.md's state machine, and each refusal."""

import pytest
from sqlalchemy import func, select

from backend import requests as refund_requests
from backend.database import engine, refunds
from backend.tests.moves import decide, go_quiet, held, start


def refunds_of(request_id: str) -> list:
    with engine().connect() as connection:
        return list(
            connection.execute(
                select(refunds).where(refunds.c.request_id == request_id)
            )
        )


def test_starting_a_waiting_request_begins_its_first_attempt(rep, agent_calls):
    request = start(rep, "REQ-1001")
    assert (request["state"], request["attempt"], request["revision"]) == (
        "working",
        1,
        1,
    )
    assert agent_calls == [{"operation": "work", "request_id": "REQ-1001"}]


def test_a_working_request_cant_be_started_again(rep):
    start(rep, "REQ-1001")
    response = rep.post("/api/requests/REQ-1001/start")
    assert response.status_code == 409
    assert response.json()["detail"] == "Request REQ-1001 is working"


def test_an_approval_within_the_limit_is_refunded_at_once(rep, agent):
    start(rep, "REQ-1001")
    response = decide(agent, "REQ-1001", amount=45.0)
    assert response.json()["state"] == "refunded"
    [refund] = refunds_of("REQ-1001")
    assert (refund.amount_cents, refund.signed_off_by) == (4500, None)
    detail = rep.get("/api/requests/REQ-1001").json()
    assert detail["decision"]["section"] == "Section 3"
    assert detail["refund"]["amount"] == 45.0


@pytest.mark.parametrize(
    ("kind", "state"), [("decline", "declined"), ("escalate", "escalated")]
)
def test_a_decline_or_an_escalation_ends_the_work_with_no_refund(
    rep, agent, kind, state
):
    start(rep, "REQ-1002")
    assert decide(agent, "REQ-1002", kind=kind).json()["state"] == state
    assert refunds_of("REQ-1002") == []


def test_an_approval_over_the_limit_is_held_with_no_refund(rep, agent):
    held(rep, agent)
    assert refunds_of("REQ-1003") == []


def test_the_same_decision_twice_gives_the_same_result_and_one_refund(rep, agent):
    start(rep, "REQ-1001")
    first = decide(agent, "REQ-1001")
    again = decide(agent, "REQ-1001")
    assert again.status_code == 200
    assert again.json() == first.json()
    assert len(refunds_of("REQ-1001")) == 1


def test_a_different_decision_for_the_same_revision_is_refused(rep, agent):
    start(rep, "REQ-1001")
    decide(agent, "REQ-1001")
    response = decide(agent, "REQ-1001", kind="decline")
    assert response.status_code == 409
    assert "different decision" in response.json()["detail"]


@pytest.mark.parametrize(("attempt", "revision"), [(2, 1), (1, 2), (0, 0)])
def test_a_decision_for_another_attempt_or_revision_is_refused(
    rep, agent, attempt, revision
):
    start(rep, "REQ-1001")
    response = decide(agent, "REQ-1001", attempt=attempt, revision=revision)
    assert response.status_code == 409
    assert "is over" in response.json()["detail"]


def test_a_decision_on_a_request_nobody_started_is_refused(agent):
    response = decide(agent, "REQ-1001", attempt=0, revision=0)
    assert response.status_code == 409
    assert response.json()["detail"] == "Request REQ-1001 is waiting"


def test_a_refund_over_the_order_total_is_refused(rep, agent):
    start(rep, "REQ-1010")
    response = decide(agent, "REQ-1010", amount=250.0)
    assert response.status_code == 422
    assert "$250.00 is more than the $180.00 paid" in response.json()["detail"]
    assert rep.get("/api/requests/REQ-1010").json()["state"] == "working"


@pytest.mark.parametrize("section", ["", "Section 99", "the usual rules"])
def test_a_decision_must_name_a_section_of_the_policy(rep, agent, section):
    start(rep, "REQ-1001")
    assert decide(agent, "REQ-1001", section=section).status_code == 422


def test_an_approval_needs_an_amount(rep, agent):
    start(rep, "REQ-1001")
    response = decide(agent, "REQ-1001", amount=None)
    assert response.status_code == 422


def test_a_supervisor_signs_off_a_held_refund(rep, agent, supervisor, agent_calls):
    decision_id = held(rep, agent)
    response = supervisor.post(
        "/api/requests/REQ-1003/sign-off", json={"decision_id": decision_id}
    )
    assert response.json()["state"] == "refunded"
    [refund] = refunds_of("REQ-1003")
    assert (refund.amount_cents, refund.signed_off_by) == (
        32000,
        "morgan.diaz@acme.example",
    )
    assert agent_calls[-1] == {
        "operation": "resume",
        "request_id": "REQ-1003",
        "answer": {"kind": "signed_off"},
    }


def test_a_rep_cant_sign_off_or_send_back(rep, agent):
    decision_id = held(rep, agent)
    sign_off = rep.post(
        "/api/requests/REQ-1003/sign-off", json={"decision_id": decision_id}
    )
    sent = rep.post(
        "/api/requests/REQ-1003/send-back",
        json={"decision_id": decision_id, "note": "Look again."},
    )
    assert (sign_off.status_code, sent.status_code) == (403, 403)
    assert (
        sign_off.json()["detail"]
        == "Only a supervisor can sign off or send back a refund"
    )


def test_a_repeated_sign_off_is_refused_and_refunds_once(rep, agent, supervisor):
    decision_id = held(rep, agent)
    body = {"decision_id": decision_id}
    supervisor.post("/api/requests/REQ-1003/sign-off", json=body)
    again = supervisor.post("/api/requests/REQ-1003/sign-off", json=body)
    assert again.status_code == 409
    assert len(refunds_of("REQ-1003")) == 1


def test_a_sign_off_for_a_decision_that_isnt_held_is_refused(rep, agent, supervisor):
    decision_id = held(rep, agent)
    stale = supervisor.post(
        "/api/requests/REQ-1003/sign-off", json={"decision_id": decision_id + 1}
    )
    assert stale.status_code == 409
    assert refunds_of("REQ-1003") == []


def test_a_send_back_starts_a_new_revision_for_the_agent(
    rep, agent, supervisor, agent_calls
):
    decision_id = held(rep, agent)
    note = "The photo shows a scratch, not a split. Check Section 3 again."
    response = supervisor.post(
        "/api/requests/REQ-1003/send-back",
        json={"decision_id": decision_id, "note": note},
    )
    request = response.json()
    assert (request["state"], request["revision"], request["decision"]) == (
        "working",
        2,
        None,
    )
    assert request["send_back"]["note"] == note
    assert agent_calls[-1]["answer"] == {
        "kind": "sent_back",
        "note": note,
        "revision": 2,
    }


def test_after_a_send_back_the_agent_decides_again_once(rep, agent, supervisor):
    decision_id = held(rep, agent)
    supervisor.post(
        "/api/requests/REQ-1003/send-back",
        json={"decision_id": decision_id, "note": "Look again."},
    )
    replay = decide(agent, "REQ-1003", amount=320.0)
    assert (replay.status_code, replay.json()["state"]) == (200, "held")
    assert rep.get("/api/requests/REQ-1003").json()["state"] == "working"
    different = decide(agent, "REQ-1003", kind="decline")
    assert different.status_code == 409
    revised = decide(agent, "REQ-1003", revision=2, kind="escalate")
    assert revised.json()["state"] == "escalated"
    assert (
        decide(agent, "REQ-1003", revision=2, kind="escalate").json() == revised.json()
    )


def test_a_replayed_decision_answers_with_what_it_did_then(rep, agent, supervisor):
    """A decision sent again after the request moved on gets the state it moved
    the request to, not where the request is now."""
    decision_id = held(rep, agent)
    supervisor.post(
        "/api/requests/REQ-1003/sign-off", json={"decision_id": decision_id}
    )
    replay = decide(agent, "REQ-1003", amount=320.0)
    assert replay.json() == {
        "request_id": "REQ-1003",
        "state": "held",
        "decision_id": decision_id,
    }
    assert len(refunds_of("REQ-1003")) == 1


def test_a_note_over_1000_characters_is_refused(rep, agent, supervisor):
    decision_id = held(rep, agent)
    response = supervisor.post(
        "/api/requests/REQ-1003/send-back",
        json={"decision_id": decision_id, "note": "x" * 1001},
    )
    assert response.status_code == 422


def test_a_failure_ends_the_attempt_and_the_request_can_start_again(rep, agent):
    start(rep, "REQ-1001")
    response = agent.post(
        "/api/requests/REQ-1001/failure",
        json={"attempt": 1, "reason": "The model was down"},
    )
    assert response.status_code == 200
    request = rep.get("/api/requests/REQ-1001").json()
    assert (request["state"], request["failure"]) == ("failed", "The model was down")
    again = start(rep, "REQ-1001")
    assert (again["state"], again["attempt"], again["failure"]) == ("working", 2, None)


def test_a_failure_on_a_finished_request_is_refused(rep, agent):
    start(rep, "REQ-1001")
    decide(agent, "REQ-1001")
    response = agent.post(
        "/api/requests/REQ-1001/failure", json={"attempt": 1, "reason": "x"}
    )
    assert response.status_code == 409


def test_steps_are_kept_for_the_current_attempt_in_any_state(rep, agent):
    start(rep, "REQ-1001")
    decide(agent, "REQ-1001")
    step = {"attempt": 1, "kind": "reply", "text": "Refunded in full under Section 3."}
    assert agent.post("/api/requests/REQ-1001/steps", json=step).status_code == 200
    kinds = [s["kind"] for s in rep.get("/api/requests/REQ-1001/steps").json()]
    assert kinds == ["started", "decision", "reply"]


def test_steps_for_an_old_attempt_are_refused(rep, agent):
    start(rep, "REQ-1001")
    agent.post("/api/requests/REQ-1001/failure", json={"attempt": 1, "reason": "x"})
    start(rep, "REQ-1001")
    old = {"attempt": 1, "kind": "reply", "text": "late"}
    response = agent.post("/api/requests/REQ-1001/steps", json=old)
    assert response.status_code == 409
    assert response.json()["detail"] == "Attempt 1 of request REQ-1001 is over"


def test_a_quiet_request_reads_as_stalled_and_can_be_taken_over(rep, agent):
    start(rep, "REQ-1001")
    go_quiet("REQ-1001", minutes=6)
    assert rep.get("/api/requests/REQ-1001").json()["state"] == "stalled"
    taken = start(rep, "REQ-1001")
    assert (taken["state"], taken["attempt"]) == ("working", 1)


def test_a_request_heard_from_recently_isnt_stalled(rep, agent):
    start(rep, "REQ-1001")
    go_quiet("REQ-1001", minutes=4)
    assert rep.get("/api/requests/REQ-1001").json()["state"] == "working"
    assert rep.post("/api/requests/REQ-1001/start").status_code == 409


def test_a_step_keeps_a_request_from_stalling(rep, agent):
    start(rep, "REQ-1001")
    go_quiet("REQ-1001", minutes=6)
    agent.post(
        "/api/requests/REQ-1001/steps",
        json={"attempt": 1, "kind": "reply", "text": "..."},
    )
    assert rep.get("/api/requests/REQ-1001").json()["state"] == "working"


def test_the_seeded_refunds_are_one_each():
    with engine().connect() as connection:
        assert (
            connection.execute(select(func.count()).select_from(refunds)).scalar_one()
            == 3
        )


def test_a_decision_that_loses_a_race_to_the_same_decision_gets_its_result(
    rep, agent, monkeypatch
):
    """Two identical decisions at once: the second read the request and found no
    decision before the first committed, so its conditional update moves
    nothing and it answers from what the first recorded."""
    start(rep, "REQ-1001")
    with engine().connect() as connection:
        before = refund_requests.find(connection, "REQ-1001")
    first = decide(agent, "REQ-1001")
    real_find, real_lookup = refund_requests.find, refund_requests.decision_for
    real_lost = refund_requests.lost_race
    stale = {"find": True, "lookup": True}
    lost: list[str] = []

    def find(connection, request_id):
        """The request as the second caller first saw it, then as it is."""
        return before if stale.pop("find", False) else real_find(connection, request_id)

    def decision_for(connection, request_id, attempt, revision):
        if stale.pop("lookup", False):
            return None
        return real_lookup(connection, request_id, attempt, revision)

    def lost_race(connection, request_id, new):
        lost.append(request_id)
        return real_lost(connection, request_id, new)

    monkeypatch.setattr(refund_requests, "find", find)
    monkeypatch.setattr(refund_requests, "decision_for", decision_for)
    monkeypatch.setattr(refund_requests, "lost_race", lost_race)
    second = decide(agent, "REQ-1001")
    assert lost == ["REQ-1001"]
    assert second.status_code == 200
    assert second.json() == first.json()
    assert len(refunds_of("REQ-1001")) == 1


def test_a_step_for_a_missing_request_is_a_404(agent):
    response = agent.post(
        "/api/requests/REQ-9999/steps",
        json={"attempt": 1, "kind": "reply", "text": "x"},
    )
    assert response.status_code == 404


@pytest.mark.parametrize("field", ["section", "reason", "decided_by"])
def test_text_of_only_spaces_is_refused_and_nothing_changes(rep, agent, field):
    start(rep, "REQ-1001")
    response = decide(agent, "REQ-1001", **{field: "   "})
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert field in response.json()["detail"]
    assert rep.get("/api/requests/REQ-1001").json()["state"] == "working"
    assert refunds_of("REQ-1001") == []


def test_a_note_of_only_spaces_is_refused(rep, agent, supervisor):
    decision_id = held(rep, agent)
    response = supervisor.post(
        "/api/requests/REQ-1003/send-back",
        json={"decision_id": decision_id, "note": "  "},
    )
    assert response.status_code == 422
    assert rep.get("/api/requests/REQ-1003").json()["state"] == "held"


def test_a_refusal_for_an_invalid_body_reads_as_one_line(agent):
    response = agent.post("/api/requests/REQ-1001/steps", json={"attempt": "x"})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, str)
    assert "attempt" in detail
    assert "kind" in detail
