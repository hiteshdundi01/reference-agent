"""The agent's API on the backend: one function per operation it calls, each
named after the operation."""

from typing import Any

from agent.connection import call


def get_request(request_id: str) -> dict[str, Any]:
    return call("GET", f"/requests/{request_id}")


def get_customer_history(request_id: str) -> list[dict[str, Any]]:
    return call("GET", f"/requests/{request_id}/history")


def get_order(order_id: str) -> dict[str, Any]:
    return call("GET", f"/orders/{order_id}")


def get_policy_section(number: int) -> dict[str, Any]:
    return call("GET", f"/policy/sections/{number}")


def record_decision(request_id: str, decision: dict[str, Any]) -> dict[str, Any]:
    return call("POST", f"/requests/{request_id}/decision", json=decision)


def record_step(request_id: str, attempt: int, kind: str, text: str) -> None:
    step = {"attempt": attempt, "kind": kind, "text": text}
    call("POST", f"/requests/{request_id}/steps", json=step)


def fail_work(request_id: str, attempt: int, reason: str) -> None:
    failure = {"attempt": attempt, "reason": reason}
    call("POST", f"/requests/{request_id}/failure", json=failure)
