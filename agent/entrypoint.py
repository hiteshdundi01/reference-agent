"""The agent's app, in the shape of Amazon Bedrock AgentCore Runtime's contract.

POST /invocations takes one operation's payload. It answers at once and works on
a thread of its own, one piece of work per request at a time in the process.
GET /ping says whether any work is going."""

import logging
import os
import threading
from collections.abc import Callable
from secrets import compare_digest
from typing import Annotated, Any, Literal

from fastapi import Body, FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from agent import api, harness, models
from agent.connection import Refused

ACCEPTED = {"accepted": True}
HEALTHY = {"healthy": True}

log = logging.getLogger(__name__)
app = FastAPI(title="Acme refund agent")


class Operation(BaseModel):
    """A payload: it names its operation and carries every input, each of the
    right type, and no other."""

    model_config = ConfigDict(extra="forbid", strict=True)


class Health(Operation):
    operation: Literal["health"]


class Work(Operation):
    operation: Literal["work"]
    request_id: str


class SignedOff(Operation):
    kind: Literal["signed_off"]


class SentBack(Operation):
    kind: Literal["sent_back"]
    note: str
    revision: int


class Resume(Operation):
    operation: Literal["resume"]
    request_id: str
    answer: Annotated[SignedOff | SentBack, Field(discriminator="kind")]


payloads: TypeAdapter[Health | Work | Resume] = TypeAdapter(
    Annotated[Health | Work | Resume, Field(discriminator="operation")]
)

# The requests being worked in this process, so that each is worked once at a time.
working: set[str] = set()
guard = threading.Lock()


def what_is_wrong(error: ValidationError) -> str:
    """Say what's wrong with a payload, without echoing its values."""
    problems = []
    for problem in error.errors():
        if problem["type"] == "union_tag_invalid":
            context = problem.get("ctx", {})
            tag = str(context.get("discriminator", "")).strip("'")
            problems.append(f"{tag}: must be one of {context.get('expected_tags')}")
            continue
        where = ".".join(str(part) for part in problem["loc"]) or "the payload"
        problems.append(f"{where}: {problem['msg']}")
    return "; ".join(problems)


def check_key(authorization: str | None) -> None:
    expected = os.getenv("AGENT_KEY", "")
    scheme, _, given = (authorization or "").partition(" ")
    right = scheme == "Bearer" and compare_digest(given.encode(), expected.encode())
    if not expected or not right:
        raise HTTPException(401, "The agent's key is missing or wrong")


def report_failure(request: dict[str, Any], error: Exception) -> None:
    """Tell the backend why the work on the attempt stopped."""
    reason = f"{type(error).__name__}: {error}"
    log.warning("Request %s failed: %s", request["id"], reason)
    try:
        api.fail_work(request["id"], request["attempt"], reason)
    except Refused as refused:
        log.warning("The backend kept %s as it was: %s", request["id"], refused.detail)


Job = Callable[[dict[str, Any]], None]


def run(request_id: str, work: Job) -> None:
    """Read the request once, then work its attempt; a failure ends that attempt,
    never a later one."""
    try:
        request = api.get_request(request_id)
        try:
            work(request)
        except Exception as error:  # any failure ends the attempt, with its reason
            report_failure(request, error)
    except Exception:  # with no request read, there is no attempt to end
        log.exception("Couldn't read request %s", request_id)
    finally:
        with guard:
            working.discard(request_id)


def take(request_id: str, work: Job) -> dict[str, Any]:
    """Start the work on a thread of its own, unless the request is being worked."""
    with guard:
        if request_id in working:
            return {"refused": f"Request {request_id} is already being worked"}
        working.add(request_id)
    threading.Thread(target=run, args=(request_id, work), daemon=True).start()
    return ACCEPTED


@app.post("/invocations")
def invocations(
    payload: Annotated[Any, Body()],
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Take one operation: the health check, working a request, or resuming one."""
    try:
        operation = payloads.validate_python(payload)
    except ValidationError as error:
        raise HTTPException(400, what_is_wrong(error)) from error
    if isinstance(operation, Health):
        return HEALTHY
    check_key(authorization)
    if isinstance(operation, Work):
        return take(
            operation.request_id,
            lambda request: harness.work(
                request, models.chat_model(), models.model_name()
            ),
        )
    answer = operation.answer.model_dump()
    return take(
        operation.request_id,
        lambda request: harness.resume(
            request, answer, models.chat_model(), models.model_name()
        ),
    )


@app.get("/ping")
def ping() -> dict[str, str]:
    """Say whether the agent is working on anything."""
    with guard:
        return {"status": "HealthyBusy" if working else "Healthy"}
