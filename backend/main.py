"""The backend's app: its routes, each a thin call into requests.py behind its
gate, and the dashboard's build when there is one."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select

from backend import agent_service, asking, auth, models
from backend import requests as refund_requests
from backend.dashboard import serve_dashboard
from backend.database import engine, users
from backend.dependencies import AgentKey, AgentOrPerson, SignedIn, Supervisor

AGENT = "agent"
WRONG_SIGN_IN = "That email and password don't match"

app = FastAPI(title="Acme refund desk")


@app.exception_handler(RequestValidationError)
def invalid(_: Request, error: RequestValidationError) -> JSONResponse:
    """Say what's wrong with a request in one line, as every refusal does, without
    echoing what was sent."""
    problems = [
        f"{'.'.join(str(part) for part in problem['loc'][1:]) or 'the body'}: "
        f"{problem['msg']}"
        for problem in error.errors()
    ]
    return JSONResponse({"detail": "; ".join(problems)}, status_code=422)


@app.exception_handler(refund_requests.Refused)
def refused(_: Request, error: refund_requests.Refused) -> JSONResponse:
    return JSONResponse({"detail": error.detail}, status_code=error.status_code)


@app.get("/api/health", operation_id="health")
def health() -> dict[str, bool]:
    """Say that the backend is up."""
    return {"healthy": True}


@app.post("/api/sign-in", operation_id="sign_in")
def sign_in(details: models.SignInDetails) -> models.SignedIn:
    """Sign a person in with their email and password."""
    with engine().connect() as connection:
        row = connection.execute(
            select(users).where(users.c.email == details.email)
        ).first()
    if row is None or not auth.password_matches(details.password, row.password_hash):
        raise HTTPException(401, WRONG_SIGN_IN)
    user = models.User(email=row.email, name=row.name, role=row.role)
    return models.SignedIn(token=auth.token_for(row.email), user=user)


@app.get("/api/me", operation_id="me")
def me(user: SignedIn) -> models.User:
    """Say who is signed in."""
    return user


@app.get("/api/requests", operation_id="list_requests")
def list_requests(_: SignedIn) -> list[models.RequestSummary]:
    """List every refund request, oldest first."""
    with engine().connect() as connection:
        return refund_requests.summaries(connection)


@app.get(
    "/api/requests/{request_id}",
    operation_id="get_request",
    tags=[AGENT],
    dependencies=[AgentOrPerson],
)
def get_request(request_id: str) -> models.RequestDetail:
    """Get a refund request with its decision, refund and latest send-back."""
    with engine().connect() as connection:
        return refund_requests.detail(connection, request_id)


@app.get(
    "/api/requests/{request_id}/history",
    operation_id="get_customer_history",
    tags=[AGENT],
    dependencies=[AgentOrPerson],
)
def get_customer_history(request_id: str) -> list[models.PastRequest]:
    """List the other refund requests of the customer who made this one."""
    with engine().connect() as connection:
        return refund_requests.history(connection, request_id)


@app.get(
    "/api/orders/{order_id}",
    operation_id="get_order",
    tags=[AGENT],
    dependencies=[AgentOrPerson],
)
def get_order(order_id: str) -> models.Order:
    """Get an order with its items, total and delivery."""
    with engine().connect() as connection:
        return refund_requests.order(connection, order_id)


@app.get(
    "/api/policy/sections/{number}",
    operation_id="get_policy_section",
    tags=[AGENT],
    dependencies=[AgentOrPerson],
)
def get_policy_section(number: int) -> models.PolicySection:
    """Get one numbered section of the refund policy."""
    with engine().connect() as connection:
        return refund_requests.policy_section(connection, number)


@app.get("/api/requests/{request_id}/steps", operation_id="list_steps")
def list_steps(request_id: str, _: SignedIn) -> list[models.Step]:
    """List every step recorded on a refund request, oldest first."""
    with engine().connect() as connection:
        return refund_requests.steps_of(connection, request_id)


@app.post("/api/requests/{request_id}/start", operation_id="start_work")
def start_work(request_id: str, user: SignedIn) -> models.RequestDetail:
    """Ask the agent to work a waiting, failed or stalled refund request."""
    asking.ask(
        lambda connection: refund_requests.start(connection, request_id, user.name),
        lambda _: agent_service.work(request_id),
        refund_requests.undo_start,
    )
    return get_request(request_id)


@app.post(
    "/api/requests/{request_id}/decision",
    operation_id="record_decision",
    tags=[AGENT],
    dependencies=[AgentKey],
)
def record_decision(request_id: str, decision: models.NewDecision) -> models.Recorded:
    """Record the agent's decision on its attempt and revision of a request."""
    with engine().begin() as connection:
        return refund_requests.record_decision(connection, request_id, decision)


@app.post(
    "/api/requests/{request_id}/steps",
    operation_id="record_step",
    tags=[AGENT],
    dependencies=[AgentKey],
)
def record_step(request_id: str, step: models.NewStep) -> models.Ok:
    """Record a step of the agent's attempt on a request."""
    with engine().begin() as connection:
        refund_requests.add_step(
            connection, request_id, step.attempt, step.kind, step.text
        )
    return models.Ok()


@app.post(
    "/api/requests/{request_id}/failure",
    operation_id="fail_work",
    tags=[AGENT],
    dependencies=[AgentKey],
)
def fail_work(request_id: str, failure: models.Failure) -> models.Ok:
    """End the agent's working attempt on a request that it couldn't finish."""
    with engine().begin() as connection:
        refund_requests.fail(connection, request_id, failure.attempt, failure.reason)
    return models.Ok()


@app.post("/api/requests/{request_id}/sign-off", operation_id="sign_off")
def sign_off(
    request_id: str, answer: models.SignOff, user: Supervisor
) -> models.RequestDetail:
    """Sign off a held refund, which issues it, and let the agent finish."""
    with engine().begin() as connection:
        refund_requests.sign_off(connection, request_id, answer.decision_id, user)
    # The refund stands whatever the agent answers; a graph it never hears of
    # stays paused and does no harm.
    agent_service.resume(request_id, {"kind": "signed_off"})
    return get_request(request_id)


@app.post("/api/requests/{request_id}/send-back", operation_id="send_back")
def send_back(
    request_id: str, answer: models.SendBackNote, user: Supervisor
) -> models.RequestDetail:
    """Send a held decision back to the agent with a note on what to look at again."""
    asking.ask(
        lambda connection: refund_requests.send_back(
            connection, request_id, answer.decision_id, answer.note, user
        ),
        lambda sent: agent_service.resume(
            request_id,
            {"kind": "sent_back", "note": sent.note, "revision": sent.revision},
        ),
        refund_requests.undo_send_back,
    )
    return get_request(request_id)


serve_dashboard(app, Path(__file__).parent.parent / "dashboard" / "dist")
