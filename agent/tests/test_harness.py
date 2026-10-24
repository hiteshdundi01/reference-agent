"""Phase 3: the agent's graph on the stub model, against the real backend."""

import pytest
from langchain_core.messages import ToolMessage

from agent import api, checkpoints, harness, tools
from agent.tests.conftest import STUB_MODEL
from agent.tests.stubs import Failing, approve, decline, escalate, reads, says, stub
from backend.database import engine, seed
from backend.tests.moves import start


def work(request_id, *replies):
    model = stub(*replies)
    harness.work(api.get_request(request_id), model, STUB_MODEL)
    return model


def resume(request_id, answer, *replies):
    model = stub(*replies)
    harness.resume(api.get_request(request_id), answer, model, STUB_MODEL)
    return model


def paused(request):
    return harness.build(stub()).get_state(harness.thread_of(request))


def kinds(rep, request_id):
    return [
        step["kind"] for step in rep.get(f"/api/requests/{request_id}/steps").json()
    ]


def held(rep):
    start(rep, "REQ-1003")
    work("REQ-1003", approve(320.0))
    return rep.get("/api/requests/REQ-1003").json()["decision"]["id"]


def send_back(supervisor, decision_id, note):
    supervisor.post(
        "/api/requests/REQ-1003/send-back",
        json={"decision_id": decision_id, "note": note},
    )
    return {"kind": "sent_back", "note": note, "revision": 2}


def test_an_approval_within_the_limit_is_refunded(rep):
    start(rep, "REQ-1001")
    work("REQ-1001", *reads("read_request", "read_order"), approve(45.0), says("Done."))
    request = rep.get("/api/requests/REQ-1001").json()
    assert request["state"] == "refunded"
    assert request["decision"]["decided_by"] == f"agent ({STUB_MODEL})"
    assert kinds(rep, "REQ-1001") == [
        "started",
        "model_call", "tool_call", "tool_result",
        "model_call", "tool_call", "tool_result",
        "model_call", "tool_call", "decision", "tool_result",
    ]  # fmt: skip


def test_every_model_call_records_its_usage(rep):
    start(rep, "REQ-1002")
    work("REQ-1002", decline())
    steps = rep.get("/api/requests/REQ-1002/steps").json()
    usage = [step["text"] for step in steps if step["kind"] == "model_call"]
    assert usage == ["1,200 tokens in, 300 out"]


def test_a_decision_ends_the_graph_without_another_model_call(rep):
    start(rep, "REQ-1002")
    model = work("REQ-1002", decline())
    assert rep.get("/api/requests/REQ-1002").json()["state"] == "declined"
    assert len(model.prompts) == 1


def test_an_escalation_ends_the_work(rep):
    start(rep, "REQ-1012")
    work("REQ-1012", escalate())
    assert rep.get("/api/requests/REQ-1012").json()["state"] == "escalated"


def test_an_approval_over_the_limit_pauses_for_a_supervisor(rep):
    held(rep)
    request = rep.get("/api/requests/REQ-1003").json()
    assert request["state"] == "held"
    assert paused(request).next == ("wait_for_supervisor",)


def test_a_sign_off_ends_the_paused_graph(rep, supervisor):
    decision_id = held(rep)
    supervisor.post(
        "/api/requests/REQ-1003/sign-off", json={"decision_id": decision_id}
    )
    model = resume("REQ-1003", {"kind": "signed_off"})
    request = rep.get("/api/requests/REQ-1003").json()
    assert request["state"] == "refunded"
    assert paused(request).next == ()
    assert model.prompts == []


def test_a_send_back_has_the_agent_decide_again_under_the_new_revision(rep, supervisor):
    note = "The photo shows a scratch, not a split."
    answer = send_back(supervisor, held(rep), note)
    model = resume("REQ-1003", answer, escalate(section="Section 3"))
    request = rep.get("/api/requests/REQ-1003").json()
    assert (request["state"], request["revision"]) == ("escalated", 2)
    assert note in model.prompts[0][-1].content


def test_a_crash_after_a_held_approval_then_a_send_back_decides_again(
    rep, supervisor, monkeypatch
):
    """The approval committed as held, but the process died before its step was
    saved. The supervisor's send-back moves the request to revision 2: the saved
    work replays under revision 1, then the graph takes the note."""
    start(rep, "REQ-1003")
    real = api.record_decision

    def then_die(request_id, decision):
        real(request_id, decision)
        raise Failing("the process died")

    monkeypatch.setattr(api, "record_decision", then_die)
    with pytest.raises(Failing):
        work("REQ-1003", approve(320.0))
    monkeypatch.setattr(api, "record_decision", real)
    decision_id = rep.get("/api/requests/REQ-1003").json()["decision"]["id"]
    answer = send_back(supervisor, decision_id, "Check the photo date.")
    model = resume("REQ-1003", answer, escalate(section="Section 3"))
    request = rep.get("/api/requests/REQ-1003").json()
    assert (request["state"], request["revision"]) == ("escalated", 2)
    assert "Check the photo date." in model.prompts[0][-1].content


def test_work_gives_a_send_back_that_never_reached_the_agent(rep, supervisor):
    answer = send_back(supervisor, held(rep), "Check the photo date.")
    assert answer["revision"] == 2
    model = work("REQ-1003", escalate(section="Section 3"))
    assert rep.get("/api/requests/REQ-1003").json()["state"] == "escalated"
    assert "Check the photo date." in model.prompts[0][-1].content


def test_a_reply_with_no_decision_gets_a_reminder(rep):
    start(rep, "REQ-1002")
    model = work("REQ-1002", says("I think it should be declined."), decline())
    assert rep.get("/api/requests/REQ-1002").json()["state"] == "declined"
    assert model.prompts[1][-1].content == harness.REMINDER


def test_the_backends_refusal_reaches_the_model_as_the_tools_result(rep):
    start(rep, "REQ-1010")
    model = work("REQ-1010", approve(250.0), approve(180.0))
    assert rep.get("/api/requests/REQ-1010").json()["state"] == "refunded"
    refused = model.prompts[1][-1]
    assert isinstance(refused, ToolMessage)
    assert str(refused.content).startswith("Refused: A refund of $250.00 is more than")
    assert "refusal" in kinds(rep, "REQ-1010")


def test_too_many_model_calls_with_no_decision_stop_the_work(rep, monkeypatch):
    monkeypatch.setattr(harness, "MAX_MODEL_CALLS", 3)
    start(rep, "REQ-1001")
    with pytest.raises(harness.TooManyModelCalls):
        work(
            "REQ-1001",
            *reads("read_request", "read_order", "read_request", "read_order"),
        )


def test_work_carries_on_from_its_checkpoint_after_a_crash(rep):
    start(rep, "REQ-1001")
    with pytest.raises(Failing):
        work(
            "REQ-1001",
            *reads("read_request", "read_order"),
            Failing("the process died"),
        )
    model = work("REQ-1001", approve(45.0))
    assert rep.get("/api/requests/REQ-1001").json()["state"] == "refunded"
    # The carried-on model sees the reads made before the crash.
    assert sum(isinstance(m, ToolMessage) for m in model.prompts[0]) == 2


def test_a_finished_request_is_never_carried_on(rep, agent):
    start(rep, "REQ-1001")
    with pytest.raises(Failing):
        work("REQ-1001", *reads("read_request"), Failing("the process died"))
    agent.post(
        "/api/requests/REQ-1001/decision",
        json={
            "attempt": 1,
            "revision": 1,
            "decision": "escalate",
            "section": "Section 6",
            "reason": "A person should look.",
            "decided_by": "a person",
        },
    )
    model = work("REQ-1001", approve(45.0))
    assert model.prompts == []
    assert rep.get("/api/requests/REQ-1001").json()["state"] == "escalated"


def test_each_attempt_is_a_thread_of_its_own(rep, agent):
    start(rep, "REQ-1001")
    agent.post("/api/requests/REQ-1001/failure", json={"attempt": 1, "reason": "x"})
    start(rep, "REQ-1001")
    work("REQ-1001", approve(45.0))
    threads = {
        checkpoint.config.get("configurable", {}).get("thread_id")
        for checkpoint in checkpoints.saver().list(None)
    }
    generation = api.get_request("REQ-1001")["generation"]
    assert threads == {f"{generation}:REQ-1001:2"}


def test_the_revision_comes_from_the_graph_not_the_context():
    assert "revision" not in tools.RunContext.__dataclass_fields__


def test_after_a_reseed_a_request_starts_afresh(rep):
    """Seeding resets attempts but not the agent's checkpoints; the new
    generation keeps the old graph out of the new attempt."""
    start(rep, "REQ-1001")
    work("REQ-1001", approve(45.0))
    seed(engine())
    start(rep, "REQ-1001")
    model = work("REQ-1001", approve(45.0))
    assert len(model.prompts) == 1
    assert rep.get("/api/requests/REQ-1001").json()["state"] == "refunded"


def test_a_decision_the_backend_cant_read_goes_back_to_the_model(rep):
    """A refusal for an invalid request, such as a reason of only spaces, reaches
    the model as the tool's result, and the attempt goes on."""
    start(rep, "REQ-1002")
    model = work("REQ-1002", decline(reason="   "), decline())
    refused = model.prompts[1][-1]
    assert isinstance(refused, ToolMessage)
    assert str(refused.content).startswith("Refused: ")
    assert "reason" in str(refused.content)
    assert rep.get("/api/requests/REQ-1002").json()["state"] == "declined"
