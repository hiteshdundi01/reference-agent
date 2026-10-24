"""The database: its tables, the engine on APP_DB, and seeding from data/.

Money is kept in whole cents and times in UTC."""

import json
import os
import secrets
from datetime import UTC, date, datetime
from functools import cache
from pathlib import Path
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    Date,
    DateTime,
    Engine,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    TypeDecorator,
    UniqueConstraint,
    create_engine,
    insert,
)

from backend import auth

DATA = Path(__file__).parent.parent / "data"
DEFAULT_DB = "app.db"


class UTCDateTime(TypeDecorator[datetime]):
    """A time kept in UTC, read back with its time zone on every database."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> Any:
        return value.astimezone(UTC).replace(tzinfo=None) if value else None

    def process_result_value(self, value: datetime | None, dialect: Any) -> Any:
        return value.replace(tzinfo=UTC) if value else None


metadata = MetaData()

users = Table(
    "users",
    metadata,
    Column("email", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("role", String, nullable=False),
    Column("password_hash", String, nullable=False),
)

customers = Table(
    "customers",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("email", String, nullable=False),
    Column("since", Date, nullable=False),
)

orders = Table(
    "orders",
    metadata,
    Column("id", String, primary_key=True),
    Column("customer_id", ForeignKey("customers.id"), nullable=False),
    Column("placed_at", Date, nullable=False),
    Column("expected_delivery", Date, nullable=False),
    Column("delivered_at", Date),
    Column("carrier_status", String, nullable=False),
    Column("items", JSON, nullable=False),
    Column("shipping_cents", Integer, nullable=False),
    Column("total_cents", Integer, nullable=False),
)

requests = Table(
    "requests",
    metadata,
    Column("id", String, primary_key=True),
    Column("order_id", ForeignKey("orders.id"), nullable=False),
    Column("customer_id", ForeignKey("customers.id"), nullable=False),
    Column("submitted_at", UTCDateTime, nullable=False),
    Column("amount_cents", Integer, nullable=False),
    Column("evidence", String, nullable=False),
    Column("reason", Text, nullable=False),
    Column("state", String, nullable=False),
    Column("attempt", Integer, nullable=False, default=0),
    Column("revision", Integer, nullable=False, default=0),
    Column("heard_at", UTCDateTime),
    Column("failure", Text),
)

decisions = Table(
    "decisions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("request_id", ForeignKey("requests.id"), nullable=False),
    Column("attempt", Integer, nullable=False),
    Column("revision", Integer, nullable=False),
    Column("decision", String, nullable=False),
    Column("amount_cents", Integer),
    Column("section", String, nullable=False),
    Column("reason", Text, nullable=False),
    Column("decided_by", String, nullable=False),
    Column("decided_at", UTCDateTime, nullable=False),
    # The state the decision moved the request to, which a replay answers with.
    Column("outcome", String, nullable=False),
    UniqueConstraint("request_id", "attempt", "revision"),
)

refunds = Table(
    "refunds",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("request_id", ForeignKey("requests.id"), nullable=False),
    Column("decision_id", ForeignKey("decisions.id"), nullable=False, unique=True),
    Column("amount_cents", Integer, nullable=False),
    Column("issued_at", UTCDateTime, nullable=False),
    Column("signed_off_by", String),
)

steps = Table(
    "steps",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("request_id", ForeignKey("requests.id"), nullable=False),
    Column("attempt", Integer, nullable=False),
    Column("at", UTCDateTime, nullable=False),
    Column("kind", String, nullable=False),
    Column("text", Text, nullable=False),
)

send_backs = Table(
    "send_backs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("request_id", ForeignKey("requests.id"), nullable=False),
    Column("attempt", Integer, nullable=False),
    Column("revision", Integer, nullable=False),
    Column("note", Text, nullable=False),
    Column("sent_by", String, nullable=False),
    Column("sent_at", UTCDateTime, nullable=False),
)

settings = Table(
    "settings",
    metadata,
    Column("name", String, primary_key=True),
    Column("value", String, nullable=False),
)

policy_sections = Table(
    "policy_sections",
    metadata,
    Column("number", Integer, primary_key=True),
    Column("title", String, nullable=False),
    Column("text", Text, nullable=False),
)


@cache
def engine_at(path: str) -> Engine:
    return create_engine(f"sqlite:///{path}")


def engine() -> Engine:
    """The engine on the database at APP_DB, read on each call so that a test can
    point it at a file of its own."""
    return engine_at(os.getenv("APP_DB", DEFAULT_DB))


def cents(dollars: float) -> int:
    return round(dollars * 100)


def read(name: str) -> Any:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def policy() -> tuple[str, list[dict[str, Any]]]:
    """The refund policy's version and its numbered sections, from its front matter
    and its "## Section N: Title" headings."""
    text = (DATA / "refund_policy.md").read_text(encoding="utf-8")
    _, front, body = text.split("---\n", 2)
    version = next(
        line.split(":", 1)[1].strip().strip('"')
        for line in front.splitlines()
        if line.startswith("version:")
    )
    sections = []
    for part in body.split("\n## Section ")[1:]:
        heading, _, words = part.partition("\n")
        number, title = heading.split(": ", 1)
        sections.append({"number": int(number), "title": title, "text": words.strip()})
    return version, sections


def order_row(order: dict[str, Any]) -> dict[str, Any]:
    delivered = order["delivered_at"]
    return {
        "id": order["id"],
        "customer_id": order["customer_id"],
        "placed_at": date.fromisoformat(order["placed_at"]),
        "expected_delivery": date.fromisoformat(order["expected_delivery"]),
        "delivered_at": date.fromisoformat(delivered) if delivered else None,
        "carrier_status": order["carrier_status"],
        "items": order["items"],
        "shipping_cents": cents(order["shipping"]),
        "total_cents": cents(order["total"]),
    }


def request_row(
    request: dict[str, Any], customer_id: str, state: str
) -> dict[str, Any]:
    return {
        "id": request["id"],
        "order_id": request["order_id"],
        "customer_id": customer_id,
        "submitted_at": datetime.fromisoformat(request["submitted_at"]),
        "amount_cents": cents(request["amount"]),
        "evidence": request["evidence"],
        "reason": request["reason"],
        "state": state,
        "attempt": 0,
        "revision": 0,
    }


def seed(on: Engine) -> None:
    """Rebuild the database from data/, every user with USER_PASSWORD."""
    metadata.drop_all(on)
    metadata.create_all(on)
    password = auth.hash_password(os.environ["USER_PASSWORD"])
    order_list = read("orders.json")
    owner = {order["id"]: order["customer_id"] for order in order_list}
    version, sections = policy()
    with on.begin() as connection:
        connection.execute(
            insert(users),
            [{**user, "password_hash": password} for user in read("users.json")],
        )
        connection.execute(
            insert(customers),
            [
                {**c, "since": date.fromisoformat(c["since"])}
                for c in read("customers.json")
            ],
        )
        connection.execute(insert(orders), [order_row(order) for order in order_list])
        waiting = [
            request_row(r, owner[r["order_id"]], "waiting")
            for r in read("requests.json")
        ]
        connection.execute(insert(requests), waiting)
        seed_past_refunds(connection, owner)
        connection.execute(
            insert(settings),
            [
                {
                    "name": "approval_limit_cents",
                    "value": str(cents(read("settings.json")["approval_limit"])),
                },
                {"name": "policy_version", "value": version},
                # Changes at each seeding, so the agent never takes up a graph
                # from before it (agent/harness.py thread_of).
                {"name": "generation", "value": secrets.token_hex(8)},
            ],
        )
        connection.execute(insert(policy_sections), sections)


def seed_past_refunds(connection: Any, owner: dict[str, str]) -> None:
    """Earlier requests, each refunded by a support rep."""
    for past in read("past_refunds.json"):
        row = request_row(past, owner[past["order_id"]], "refunded")
        connection.execute(insert(requests), {**row, "attempt": 1, "revision": 1})
        decided_at = datetime.fromisoformat(past["decided_at"])
        decision = connection.execute(
            insert(decisions).returning(decisions.c.id),
            {
                "request_id": past["id"],
                "attempt": 1,
                "revision": 1,
                "decision": "approve",
                "amount_cents": row["amount_cents"],
                "section": past["section"],
                "reason": past["reason"],
                "decided_by": "a support rep",
                "decided_at": decided_at,
                "outcome": "refunded",
            },
        ).scalar_one()
        connection.execute(
            insert(refunds),
            {
                "request_id": past["id"],
                "decision_id": decision,
                "amount_cents": row["amount_cents"],
                "issued_at": decided_at,
            },
        )
