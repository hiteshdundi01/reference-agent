"""The agent's tools, and the context they read. Every id comes from the run's
context, never from the model, and the backend's refusals go back to the model as
the tool's result."""

from dataclasses import dataclass
from typing import Any, Literal

from langchain.tools import ToolRuntime, tool

from agent import api
from agent.connection import Refused

APPROVE = "approve_refund"
DECLINE_OR_ESCALATE = "decline_or_escalate"
DECISIONS = {APPROVE, DECLINE_OR_ESCALATE}


@dataclass(frozen=True)
class RunContext:
    """What a run's tools need to know that doesn't change within an attempt: the
    request, its order, the attempt, and the model, which decisions name. The
    revision is in the graph's saved state, since a send-back changes it."""

    request_id: str
    order_id: str
    attempt: int
    model: str


def refusal(error: Refused) -> str:
    """How a model is told the backend refused a call."""
    return f"Refused: {error.detail}"


@tool
def read_request(runtime: ToolRuntime[RunContext]) -> dict[str, Any]:
    """Read the refund request: the customer's reason, the amount asked for, its
    evidence, and any note a supervisor sent back."""
    return api.get_request(runtime.context.request_id)


@tool
def read_order(runtime: ToolRuntime[RunContext]) -> dict[str, Any]:
    """Read the order: its items, whether each is final sale, shipping, the total
    paid, and its delivery."""
    return api.get_order(runtime.context.order_id)


@tool
def read_customer_history(runtime: ToolRuntime[RunContext]) -> list[dict[str, Any]]:
    """Read the customer's other refund requests, newest first."""
    return api.get_customer_history(runtime.context.request_id)


@tool
def read_policy_section(
    number: int, runtime: ToolRuntime[RunContext]
) -> dict[str, Any]:
    """Read one numbered section of the refund policy (1 to 9)."""
    return api.get_policy_section(number)


def recorded(
    runtime: ToolRuntime[RunContext], decision: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    """Record a decision on the attempt and the revision the graph is on, and say
    where it left the request."""
    context = runtime.context
    body = {
        "attempt": context.attempt,
        "revision": runtime.state["revision"],
        "decided_by": f"agent ({context.model})",
        **decision,
    }
    result = api.record_decision(context.request_id, body)
    return f"Recorded. The request is now {result['state']}.", result


@tool(response_format="content_and_artifact")
def approve_refund(
    amount: float, section: str, reason: str, runtime: ToolRuntime[RunContext]
) -> tuple[str, dict[str, Any]]:
    """Approve a refund of the amount, in dollars, naming the policy section it
    relies on (such as "Section 3") and the reason in two or three sentences."""
    decision = {
        "decision": "approve",
        "amount": amount,
        "section": section,
        "reason": reason,
    }
    return recorded(runtime, decision)


@tool(response_format="content_and_artifact")
def decline_or_escalate(
    decision: Literal["decline", "escalate"],
    section: str,
    reason: str,
    runtime: ToolRuntime[RunContext],
) -> tuple[str, dict[str, Any]]:
    """Decline the request, or escalate it to a person, naming the policy section
    it relies on and the reason in two or three sentences."""
    return recorded(
        runtime, {"decision": decision, "section": section, "reason": reason}
    )


TOOLS = [
    read_request,
    read_order,
    read_customer_history,
    read_policy_section,
    approve_refund,
    decline_or_escalate,
]
