"""The API's models. Money comes in as dollars with at most two decimal places and
goes out as dollars."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

State = Literal[
    "waiting",
    "working",
    "stalled",
    "held",
    "refunded",
    "declined",
    "escalated",
    "failed",
]
Role = Literal["rep", "supervisor"]
StepKind = Literal[
    "started", "model_call", "reply", "tool_call", "tool_result", "refusal", "decision",
    "signed_off", "sent_back", "failure",
]  # fmt: skip
Dollars = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]
# Text that must say something: spaces alone are refused.
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Strict(BaseModel):
    """A request body: every input of the right type, and no other."""

    model_config = ConfigDict(extra="forbid")


class SignInDetails(Strict):
    email: str
    password: str


class User(BaseModel):
    email: str
    name: str
    role: Role


class SignedIn(BaseModel):
    token: str
    user: User


class Item(BaseModel):
    sku: str
    name: str
    price: float
    quantity: int
    final_sale: bool


class Order(BaseModel):
    id: str
    customer_id: str
    placed_at: date
    expected_delivery: date
    delivered_at: date | None
    carrier_status: str
    items: list[Item]
    shipping: float
    total: float


class Decision(BaseModel):
    id: int
    decision: Literal["approve", "decline", "escalate"]
    amount: float | None
    section: str
    reason: str
    decided_by: str
    decided_at: datetime


class Refund(BaseModel):
    amount: float
    issued_at: datetime
    signed_off_by: str | None


class SendBack(BaseModel):
    note: str
    sent_by: str
    sent_at: datetime
    revision: int


class RequestSummary(BaseModel):
    id: str
    customer_name: str
    order_id: str
    amount: float
    submitted_at: datetime
    state: State


class RequestDetail(RequestSummary):
    customer_id: str
    generation: str
    evidence: str
    reason: str
    attempt: int
    revision: int
    failure: str | None
    decision: Decision | None
    refund: Refund | None
    send_back: SendBack | None


class PastRequest(BaseModel):
    id: str
    order_id: str
    submitted_at: datetime
    amount: float
    state: State
    refunded: float | None


class PolicySection(BaseModel):
    number: int
    title: str
    text: str
    version: str


class Step(BaseModel):
    id: int
    attempt: int
    at: datetime
    kind: StepKind
    text: str


class OfAttempt(Strict):
    """What the agent says about the attempt and revision it is working on."""

    attempt: int
    revision: int


class Approve(OfAttempt):
    decision: Literal["approve"]
    amount: Dollars
    section: Text
    reason: Text
    decided_by: Text


class DeclineOrEscalate(OfAttempt):
    decision: Literal["decline", "escalate"]
    section: Text
    reason: Text
    decided_by: Text


NewDecision = Annotated[Approve | DeclineOrEscalate, Field(discriminator="decision")]


class Recorded(BaseModel):
    request_id: str
    state: State
    decision_id: int


class NewStep(Strict):
    attempt: int
    kind: StepKind
    text: str


class Failure(Strict):
    attempt: int
    reason: Text


class SignOff(Strict):
    decision_id: int


class SendBackNote(Strict):
    decision_id: int
    note: Annotated[Text, StringConstraints(max_length=1000)]


class Ok(BaseModel):
    ok: Literal[True] = True
