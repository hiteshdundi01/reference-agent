"""Refund requests and every move they make (the state machine in docs/PLAN.md).

Each move is one conditional update on the request's state, attempt and revision
that checks its row count, so only one caller can make it. A refund is only ever
written here, inside the transaction of the move that issues it."""

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Connection, Row, delete, exists, insert, select, update

from backend import models
from backend.database import cents as to_cents
from backend.database import (
    customers,
    decisions,
    orders,
    policy_sections,
    refunds,
    requests,
    send_backs,
    settings,
    steps,
)

STALL_AFTER = timedelta(minutes=5)
SECTION = re.compile(r"Section (\d+)")


class Refused(Exception):
    """A request the backend won't carry out, with its status and reason."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code, self.detail = status_code, detail


def now() -> datetime:
    return datetime.now(UTC)


def money(cents: int) -> str:
    """An amount as people read it, such as $1,250.00."""
    return f"${cents / 100:,.2f}"


def dollars(cents: int | None) -> float | None:
    return None if cents is None else cents / 100


def state_of(request: Row[Any]) -> models.State:
    """The request's state as people see it: working, or stalled once the agent
    hasn't recorded a step for STALL_AFTER."""
    if request.state == "working" and request.heard_at < now() - STALL_AFTER:
        return "stalled"
    return request.state


def find(connection: Connection, request_id: str) -> Row[Any]:
    request = connection.execute(
        select(requests).where(requests.c.id == request_id)
    ).first()
    if request is None:
        raise Refused(404, f"There is no request {request_id}")
    return request


def wrong_state(request: Row[Any]) -> Refused:
    return Refused(409, f"Request {request.id} is {state_of(request)}")


def setting(connection: Connection, name: str) -> str:
    return connection.execute(
        select(settings.c.value).where(settings.c.name == name)
    ).scalar_one()


def add_step(
    connection: Connection, request_id: str, attempt: int, kind: str, text: str
) -> int:
    """Record a step of an attempt and hear from the agent; a step for an attempt
    that is over is refused."""
    heard = connection.execute(
        update(requests)
        .where(requests.c.id == request_id, requests.c.attempt == attempt)
        .values(heard_at=now())
    )
    if heard.rowcount != 1:
        find(connection, request_id)
        raise Refused(409, f"Attempt {attempt} of request {request_id} is over")
    return connection.execute(
        insert(steps).returning(steps.c.id),
        {
            "request_id": request_id,
            "attempt": attempt,
            "at": now(),
            "kind": kind,
            "text": text,
        },
    ).scalar_one()


# Reading


def summaries(connection: Connection) -> list[models.RequestSummary]:
    rows = connection.execute(
        select(requests, customers.c.name.label("customer_name"))
        .join(customers, customers.c.id == requests.c.customer_id)
        .order_by(requests.c.submitted_at)
    )
    return [summary_of(row, row.customer_name) for row in rows]


def summary_of(row: Row[Any], customer_name: str) -> models.RequestSummary:
    return models.RequestSummary(
        id=row.id,
        customer_name=customer_name,
        order_id=row.order_id,
        amount=row.amount_cents / 100,
        submitted_at=row.submitted_at,
        state=state_of(row),
    )


def current_decision(connection: Connection, request: Row[Any]) -> Row[Any] | None:
    """The decision of the request's attempt and revision, if it has one."""
    return decision_for(connection, request.id, request.attempt, request.revision)


def detail(connection: Connection, request_id: str) -> models.RequestDetail:
    request = find(connection, request_id)
    name = connection.execute(
        select(customers.c.name).where(customers.c.id == request.customer_id)
    ).scalar_one()
    decision = current_decision(connection, request)
    refund = connection.execute(
        select(refunds).where(refunds.c.request_id == request_id)
    ).first()
    sent_back = connection.execute(
        select(send_backs)
        .where(
            send_backs.c.request_id == request_id,
            send_backs.c.attempt == request.attempt,
        )
        .order_by(send_backs.c.revision.desc())
    ).first()
    return models.RequestDetail(
        **summary_of(request, name).model_dump(),
        customer_id=request.customer_id,
        generation=setting(connection, "generation"),
        evidence=request.evidence,
        reason=request.reason,
        attempt=request.attempt,
        revision=request.revision,
        failure=request.failure,
        decision=decision_of(decision) if decision else None,
        refund=refund_of(refund) if refund else None,
        send_back=send_back_of(sent_back) if sent_back else None,
    )


def decision_of(row: Row[Any]) -> models.Decision:
    return models.Decision(
        id=row.id,
        decision=row.decision,
        amount=dollars(row.amount_cents),
        section=row.section,
        reason=row.reason,
        decided_by=row.decided_by,
        decided_at=row.decided_at,
    )


def refund_of(row: Row[Any]) -> models.Refund:
    return models.Refund(
        amount=row.amount_cents / 100,
        issued_at=row.issued_at,
        signed_off_by=row.signed_off_by,
    )


def send_back_of(row: Row[Any]) -> models.SendBack:
    return models.SendBack(
        note=row.note, sent_by=row.sent_by, sent_at=row.sent_at, revision=row.revision
    )


def order(connection: Connection, order_id: str) -> models.Order:
    row = connection.execute(select(orders).where(orders.c.id == order_id)).first()
    if row is None:
        raise Refused(404, f"There is no order {order_id}")
    return models.Order(
        **row._asdict()
        | {"shipping": row.shipping_cents / 100, "total": row.total_cents / 100}
    )


def history(connection: Connection, request_id: str) -> list[models.PastRequest]:
    """The customer's other requests, newest first."""
    request = find(connection, request_id)
    rows = connection.execute(
        select(requests, refunds.c.amount_cents.label("refunded_cents"))
        .outerjoin(refunds, refunds.c.request_id == requests.c.id)
        .where(
            requests.c.customer_id == request.customer_id, requests.c.id != request_id
        )
        .order_by(requests.c.submitted_at.desc())
    )
    return [
        models.PastRequest(
            id=row.id,
            order_id=row.order_id,
            submitted_at=row.submitted_at,
            amount=row.amount_cents / 100,
            state=state_of(row),
            refunded=dollars(row.refunded_cents),
        )
        for row in rows
    ]


def policy_section(connection: Connection, number: int) -> models.PolicySection:
    row = connection.execute(
        select(policy_sections).where(policy_sections.c.number == number)
    ).first()
    if row is None:
        raise Refused(404, f"The refund policy has no section {number}")
    return models.PolicySection(
        **row._asdict(), version=setting(connection, "policy_version")
    )


def steps_of(connection: Connection, request_id: str) -> list[models.Step]:
    find(connection, request_id)
    rows = connection.execute(
        select(steps).where(steps.c.request_id == request_id).order_by(steps.c.id)
    )
    return [models.Step(**row._asdict()) for row in rows]


# Starting and failing


@dataclass(frozen=True)
class Started:
    """What start_work changed, so that it can be undone."""

    request_id: str
    attempt: int
    before: dict[str, Any]
    step_id: int


def start(connection: Connection, request_id: str, by: str) -> Started:
    """Start a new attempt on a waiting or failed request, or take over a stalled
    one on its current attempt."""
    request = find(connection, request_id)
    before = {
        "state": request.state,
        "attempt": request.attempt,
        "revision": request.revision,
        "heard_at": request.heard_at,
        "failure": request.failure,
    }
    if request.state in ("waiting", "failed"):
        moved = connection.execute(
            update(requests)
            .where(
                requests.c.id == request_id,
                requests.c.state == request.state,
                requests.c.attempt == request.attempt,
            )
            .values(
                state="working",
                attempt=request.attempt + 1,
                revision=1,
                heard_at=now(),
                failure=None,
            )
        )
        attempt, text = (
            request.attempt + 1,
            f"{by} started attempt {request.attempt + 1}",
        )
    elif state_of(request) == "stalled":
        moved = connection.execute(
            update(requests)
            .where(requests.c.id == request_id, requests.c.heard_at == request.heard_at)
            .values(heard_at=now())
        )
        attempt, text = (
            request.attempt,
            f"{by} took over the stalled attempt {request.attempt}",
        )
    else:
        raise wrong_state(request)
    if moved.rowcount != 1:
        raise wrong_state(find(connection, request_id))
    step_id = add_step(connection, request_id, attempt, "started", text)
    return Started(request_id, attempt, before, step_id)


def nothing_since(request_id: str, step_id: int) -> Any:
    """No step has been recorded on the request since this one."""
    return ~exists().where(steps.c.request_id == request_id, steps.c.id > step_id)


def undo_start(connection: Connection, started: Started) -> None:
    """Put a request back as it was before start_work, when the agent didn't take
    the work and nothing has happened since."""
    undone = connection.execute(
        update(requests)
        .where(
            requests.c.id == started.request_id,
            requests.c.state == "working",
            requests.c.attempt == started.attempt,
            nothing_since(started.request_id, started.step_id),
        )
        .values(**started.before)
    )
    if undone.rowcount == 1:
        connection.execute(delete(steps).where(steps.c.id == started.step_id))


def fail(connection: Connection, request_id: str, attempt: int, reason: str) -> None:
    """End a working attempt the agent couldn't finish."""
    moved = connection.execute(
        update(requests)
        .where(
            requests.c.id == request_id,
            requests.c.state == "working",
            requests.c.attempt == attempt,
        )
        .values(state="failed", failure=reason)
    )
    if moved.rowcount != 1:
        raise wrong_state(find(connection, request_id))
    add_step(connection, request_id, attempt, "failure", reason)


# Deciding


def record_decision(
    connection: Connection,
    request_id: str,
    new: models.Approve | models.DeclineOrEscalate,
) -> models.Recorded:
    """Record the agent's decision on its attempt and revision. The decision
    already recorded for them, sent again, gets what it was recorded with, even
    once the request has moved on; a refund within the limit is issued with it."""
    request = find(connection, request_id)
    stored = decision_for(connection, request_id, new.attempt, new.revision)
    if stored is not None:
        return replayed(request, stored, new)
    if (new.attempt, new.revision) != (request.attempt, request.revision):
        raise Refused(
            409,
            f"Attempt {new.attempt}, revision {new.revision} of request "
            f"{request_id} is over",
        )
    if request.state != "working":
        raise wrong_state(request)
    amount = check_decision(connection, request, new)
    to = decided_state(connection, new, amount)
    moved = connection.execute(
        update(requests)
        .where(
            requests.c.id == request_id,
            requests.c.state == "working",
            requests.c.attempt == new.attempt,
            requests.c.revision == new.revision,
        )
        .values(state=to, heard_at=now())
    )
    if moved.rowcount != 1:
        return lost_race(connection, request_id, new)
    decision_id = connection.execute(
        insert(decisions).returning(decisions.c.id),
        {
            "request_id": request_id,
            "attempt": new.attempt,
            "revision": new.revision,
            "decision": new.decision,
            "amount_cents": amount,
            "section": new.section,
            "reason": new.reason,
            "decided_by": new.decided_by,
            "decided_at": now(),
            "outcome": to,
        },
    ).scalar_one()
    if amount is not None and to == "refunded":
        issue_refund(connection, request_id, decision_id, amount, None)
    add_step(connection, request_id, new.attempt, "decision", describe(new, to, amount))
    return models.Recorded(request_id=request_id, state=to, decision_id=decision_id)


def lost_race(
    connection: Connection,
    request_id: str,
    new: models.Approve | models.DeclineOrEscalate,
) -> models.Recorded:
    """Answer a decision whose move another caller made first: the same decision
    gets what was recorded; anything else is refused."""
    request = find(connection, request_id)
    stored = decision_for(connection, request_id, new.attempt, new.revision)
    if stored is None:
        raise wrong_state(request)
    return replayed(request, stored, new)


def decision_for(
    connection: Connection, request_id: str, attempt: int, revision: int
) -> Row[Any] | None:
    """The decision recorded for an attempt and revision of a request, if any."""
    return connection.execute(
        select(decisions).where(
            decisions.c.request_id == request_id,
            decisions.c.attempt == attempt,
            decisions.c.revision == revision,
        )
    ).first()


def check_decision(
    connection: Connection,
    request: Row[Any],
    new: models.Approve | models.DeclineOrEscalate,
) -> int | None:
    """Check a decision against the rules and return an approval's amount in
    cents."""
    found = SECTION.search(new.section)
    if (
        found is None
        or not connection.execute(
            select(policy_sections.c.number).where(
                policy_sections.c.number == int(found.group(1))
            )
        ).first()
    ):
        raise Refused(422, f'"{new.section}" isn\'t a section of the refund policy')
    if not isinstance(new, models.Approve):
        return None
    amount = to_cents(float(new.amount))
    total = connection.execute(
        select(orders.c.total_cents).where(orders.c.id == request.order_id)
    ).scalar_one()
    if amount > total:
        raise Refused(
            422,
            f"A refund of {money(amount)} is more than the {money(total)} paid "
            "for the order",
        )
    return amount


def decided_state(
    connection: Connection,
    new: models.Approve | models.DeclineOrEscalate,
    amount: int | None,
) -> models.State:
    if new.decision == "decline":
        return "declined"
    if new.decision == "escalate":
        return "escalated"
    limit = int(setting(connection, "approval_limit_cents"))
    return "refunded" if amount is not None and amount <= limit else "held"


def replayed(
    request: Row[Any], stored: Row[Any], new: models.Approve | models.DeclineOrEscalate
) -> models.Recorded:
    """The answer to a decision recorded before: the same one again gets what was
    recorded, and a different one is refused."""
    amount = to_cents(float(new.amount)) if isinstance(new, models.Approve) else None
    same = (stored.decision, stored.amount_cents, stored.section, stored.reason) == (
        new.decision,
        amount,
        new.section,
        new.reason,
    )
    if not same:
        raise Refused(
            409, f"A different decision is already recorded for request {request.id}"
        )
    return models.Recorded(
        request_id=request.id, state=stored.outcome, decision_id=stored.id
    )


def describe(
    new: models.Approve | models.DeclineOrEscalate, to: str, amount: int | None
) -> str:
    if amount is not None:
        held = ", held for a supervisor" if to == "held" else ""
        return f"Approved {money(amount)}{held} ({new.section}): {new.reason}"
    verb = "Declined" if new.decision == "decline" else "Escalated"
    return f"{verb} ({new.section}): {new.reason}"


def issue_refund(
    connection: Connection,
    request_id: str,
    decision_id: int,
    amount: int,
    signed_off_by: str | None,
) -> None:
    connection.execute(
        insert(refunds),
        {
            "request_id": request_id,
            "decision_id": decision_id,
            "amount_cents": amount,
            "issued_at": now(),
            "signed_off_by": signed_off_by,
        },
    )


# A supervisor's answer


def held_decision(
    connection: Connection, request: Row[Any], decision_id: int
) -> Row[Any]:
    """The held decision a supervisor is answering, which must be the one they
    were shown."""
    decision = current_decision(connection, request)
    if request.state != "held" or decision is None or decision.id != decision_id:
        raise Refused(
            409,
            f"Decision {decision_id} isn't the one waiting for a supervisor on "
            f"request {request.id}",
        )
    return decision


def move_held(connection: Connection, request: Row[Any], **values: Any) -> None:
    moved = connection.execute(
        update(requests)
        .where(
            requests.c.id == request.id,
            requests.c.state == "held",
            requests.c.attempt == request.attempt,
            requests.c.revision == request.revision,
        )
        .values(**values)
    )
    if moved.rowcount != 1:
        raise wrong_state(find(connection, request.id))


def sign_off(
    connection: Connection, request_id: str, decision_id: int, supervisor: models.User
) -> None:
    """Issue a held refund on a supervisor's sign-off."""
    request = find(connection, request_id)
    decision = held_decision(connection, request, decision_id)
    move_held(connection, request, state="refunded")
    issue_refund(
        connection, request_id, decision.id, decision.amount_cents, supervisor.email
    )
    add_step(
        connection,
        request_id,
        request.attempt,
        "signed_off",
        f"{supervisor.name} signed off the refund of {money(decision.amount_cents)}",
    )


@dataclass(frozen=True)
class SentBack:
    """What send_back changed, so that it can be undone."""

    request_id: str
    attempt: int
    revision: int
    send_back_id: int
    step_id: int
    note: str


def send_back(
    connection: Connection,
    request_id: str,
    decision_id: int,
    note: str,
    supervisor: models.User,
) -> SentBack:
    """Send a held decision back to the agent with a supervisor's note, as a new
    revision of the attempt."""
    request = find(connection, request_id)
    held_decision(connection, request, decision_id)
    revision = request.revision + 1
    move_held(connection, request, state="working", revision=revision, heard_at=now())
    send_back_id = connection.execute(
        insert(send_backs).returning(send_backs.c.id),
        {
            "request_id": request_id,
            "attempt": request.attempt,
            "revision": revision,
            "note": note,
            "sent_by": supervisor.email,
            "sent_at": now(),
        },
    ).scalar_one()
    step_id = add_step(
        connection,
        request_id,
        request.attempt,
        "sent_back",
        f"{supervisor.name} sent the decision back: {note}",
    )
    return SentBack(request_id, request.attempt, revision, send_back_id, step_id, note)


def undo_send_back(connection: Connection, sent: SentBack) -> None:
    """Put a request back as it was before send_back, when the agent didn't take
    the work and nothing has happened since."""
    undone = connection.execute(
        update(requests)
        .where(
            requests.c.id == sent.request_id,
            requests.c.state == "working",
            requests.c.attempt == sent.attempt,
            requests.c.revision == sent.revision,
            nothing_since(sent.request_id, sent.step_id),
        )
        .values(state="held", revision=sent.revision - 1)
    )
    if undone.rowcount != 1:
        return
    connection.execute(delete(send_backs).where(send_backs.c.id == sent.send_back_id))
    connection.execute(delete(steps).where(steps.c.id == sent.step_id))
