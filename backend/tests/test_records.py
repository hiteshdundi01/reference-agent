"""Phase 1: the records, signing in, the gates and the API's rules."""

import pytest

from api_rules import rule_breaks
from backend.main import app
from backend.tests.credentials import TEST_PASSWORD

READS = (
    "/api/requests/REQ-1001",
    "/api/requests/REQ-1001/history",
    "/api/orders/ORD-5001",
    "/api/policy/sections/3",
)
AGENT_ROUTES = (
    ("/api/requests/REQ-1001/decision", {}),
    ("/api/requests/REQ-1001/steps", {}),
    ("/api/requests/REQ-1001/failure", {}),
)


def test_the_queue_holds_the_seeded_requests(rep):
    queue = rep.get("/api/requests").json()
    assert [r["state"] for r in queue].count("waiting") == 12
    assert [r["state"] for r in queue].count("refunded") == 3
    assert queue[0]["id"] == "REQ-0901"


def test_a_request_reads_in_full(rep):
    request = rep.get("/api/requests/REQ-1001").json()
    assert request["customer_name"] == "Avery Brooks"
    assert request["amount"] == 45.0
    assert request["decision"] is None
    assert request["attempt"] == 0


def test_an_order_reads_in_dollars(rep):
    order = rep.get("/api/orders/ORD-5009").json()
    assert order["total"] == 129.99
    assert order["shipping"] == 9.99
    assert order["items"][0]["name"] == "Accent chair"


def test_a_customers_history_leaves_out_the_request_itself(rep):
    history = rep.get("/api/requests/REQ-1007/history").json()
    assert [past["id"] for past in history] == ["REQ-0903", "REQ-0902", "REQ-0901"]
    assert history[0]["refunded"] == 55.0


def test_a_policy_section_reads_with_the_policys_version(rep):
    section = rep.get("/api/policy/sections/7").json()
    assert section["title"] == "Repeated requests"
    assert section["version"] == "2026.1"
    assert rep.get("/api/policy/sections/99").status_code == 404


def test_a_missing_request_is_a_404(rep):
    response = rep.get("/api/requests/REQ-9999")
    assert response.status_code == 404
    assert response.json()["detail"] == "There is no request REQ-9999"


def test_signing_in_gives_a_token_that_opens_the_routes(anonymous):
    response = anonymous.post(
        "/api/sign-in",
        json={"email": "sam.okafor@acme.example", "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    token = response.json()["token"]
    me = anonymous.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json() == {
        "email": "sam.okafor@acme.example",
        "name": "Sam Okafor",
        "role": "rep",
    }


@pytest.mark.parametrize(
    ("email", "password"),
    [("sam.okafor@acme.example", "wrong"), ("nobody@acme.example", TEST_PASSWORD)],
)
def test_a_wrong_sign_in_is_refused(anonymous, email, password):
    response = anonymous.post(
        "/api/sign-in", json={"email": email, "password": password}
    )
    assert response.status_code == 401


def test_every_page_needs_a_sign_in(anonymous):
    assert anonymous.get("/api/requests").status_code == 401
    bad = anonymous.get(
        "/api/requests", headers={"Authorization": "Bearer not-a-token"}
    )
    assert bad.status_code == 401


@pytest.mark.parametrize("path", READS)
def test_the_reads_both_make_take_the_key_or_a_sign_in(agent, rep, anonymous, path):
    assert agent.get(path).status_code == 200
    assert rep.get(path).status_code == 200
    assert anonymous.get(path).status_code == 401


def test_the_agents_key_never_stands_in_for_a_person(agent):
    response = agent.get("/api/requests")
    assert response.status_code == 403
    assert "agent's key" in response.json()["detail"]


@pytest.mark.parametrize(("path", "body"), AGENT_ROUTES)
def test_a_persons_sign_in_never_opens_the_agents_routes(rep, path, body):
    assert rep.post(path, json=body).status_code == 403


@pytest.mark.parametrize(("path", "body"), AGENT_ROUTES)
def test_with_no_key_set_the_agents_routes_are_closed(agent, monkeypatch, path, body):
    monkeypatch.delenv("AGENT_KEY")
    response = agent.post(path, json=body)
    assert response.status_code == 401
    assert "No agent key" in response.json()["detail"]


def test_a_wrong_key_is_refused(agent):
    response = agent.get("/api/requests/REQ-1001", headers={"X-API-Key": "wrong"})
    assert response.status_code == 401


def test_every_operation_keeps_the_apis_rules():
    assert rule_breaks(app.openapi()) == []


def test_the_rules_catch_an_optional_input_on_an_agent_operation():
    schema = {
        "paths": {
            "/x": {
                "post": {
                    "operationId": "x",
                    "description": "Do x.",
                    "tags": ["agent"],
                    "parameters": [{"name": "limit", "required": False}],
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {"$ref": "#/c/X"}}},
                    },
                }
            },
            "/y": {"get": {"description": "Two\nlines."}},
        },
        "components": {
            "schemas": {"X": {"properties": {"a": {}, "b": {}}, "required": ["a"]}}
        },
    }
    assert rule_breaks(schema) == [
        "POST /x: limit is optional",
        "POST /x: X.b is optional",
        "GET /y has no operation id",
        "GET /y needs a one-line description",
    ]
