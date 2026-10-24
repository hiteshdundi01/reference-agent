"""The agent's graph and how it is run.

The model decides; the code makes sure a decision is recorded, pauses for a
supervisor when the backend holds a refund, and records every step. Each attempt
on a request is a thread of its own, with its progress saved after every step."""

from collections.abc import Callable
from pathlib import Path
from typing import Any, NotRequired, cast

import httpx
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.runtime import Runtime
from langgraph.types import Command, RetryPolicy, interrupt

from agent import api, checkpoints
from agent.connection import Refused
from agent.models import usage_of
from agent.tools import DECISIONS, TOOLS, RunContext, refusal

INSTRUCTIONS = (Path(__file__).parent / "instructions.md").read_text(encoding="utf-8")
MAX_MODEL_CALLS = 20
REMINDER = (
    "You haven't recorded a decision. Record one with approve_refund or "
    "decline_or_escalate."
)
SENT_BACK = (
    "A supervisor sent your decision back with this note:\n\n{note}\n\n"
    "Check the note against the refund policy and decide again."
)
# Only the trip to the backend is retried here; model providers' own clients
# retry their rate limits and server errors.
RETRY = RetryPolicy(
    max_attempts=3, retry_on=lambda error: isinstance(error, httpx.TransportError)
)

Graph = CompiledStateGraph[Any, RunContext, Any, Any]


class TooManyModelCalls(Exception):
    """The model was called MAX_MODEL_CALLS times without a decision."""


class State(MessagesState):
    """The conversation, the revision of the attempt it is on, and the request's
    state once a decision moved it."""

    revision: int
    decided: NotRequired[str | None]


def short(text: Any, length: int = 500) -> str:
    words = str(text)
    return words if len(words) <= length else words[: length - 1] + "…"


def record(context: RunContext, kind: str, text: str) -> None:
    api.record_step(context.request_id, context.attempt, kind, text)


# The nodes


def model_node(llm: Runnable[Any, Any]) -> Callable[..., dict[str, Any]]:
    """The node that calls the model, at most MAX_MODEL_CALLS times."""

    def agent(state: State, *, runtime: Runtime[RunContext]) -> dict[str, Any]:
        calls = sum(isinstance(message, AIMessage) for message in state["messages"])
        if calls >= MAX_MODEL_CALLS:
            raise TooManyModelCalls(f"{MAX_MODEL_CALLS} model calls with no decision")
        reply = llm.invoke([SystemMessage(INSTRUCTIONS), *state["messages"]])
        record(runtime.context, "model_call", usage_of(reply))
        if reply.text:
            record(runtime.context, "reply", short(reply.text))
        return {"messages": [reply]}

    return agent


def recorded_tool_call(request: ToolCallRequest, execute: Callable[..., Any]) -> Any:
    """Run a tool call and record it and its result as steps. The backend's
    refusal goes back to the model as the result; any other error is raised, for
    the node's retry policy or the attempt's failure."""
    context = cast(RunContext, request.runtime.context)
    call = request.tool_call
    record(context, "tool_call", f"{call['name']}({short(call['args'], 200)})")
    try:
        result = execute(request)
    except Refused as error:
        record(context, "refusal", error.detail)
        return ToolMessage(
            refusal(error), name=call["name"], tool_call_id=call["id"], status="error"
        )
    if isinstance(result, ToolMessage):
        record(context, "tool_result", short(result.content))
    return result


def after_agent(state: State) -> str:
    last = state["messages"][-1]
    return "tools" if isinstance(last, AIMessage) and last.tool_calls else "remind"


def remind(state: State) -> dict[str, Any]:
    return {"messages": [HumanMessage(REMINDER)]}


def decided(state: State) -> dict[str, Any]:
    """Note where the latest decision left the request, from its tool's result."""
    for message in reversed(state["messages"]):
        if not isinstance(message, ToolMessage):
            break
        if message.name in DECISIONS and message.artifact:
            return {"decided": message.artifact["state"]}
    return {"decided": None}


def after_decided(state: State) -> str:
    outcome = state.get("decided")
    if outcome == "held":
        return "wait_for_supervisor"
    return END if outcome else "agent"


def wait_for_supervisor(state: State) -> Command[str]:
    """Pause until a supervisor signs the refund off or sends it back."""
    answer = interrupt({"waiting_for": "a supervisor"})
    if answer["kind"] == "signed_off":
        return Command(goto=END)
    note = HumanMessage(SENT_BACK.format(note=answer["note"]))
    update = {"messages": [note], "decided": None, "revision": answer["revision"]}
    return Command(goto="agent", update=update)


def build(model: BaseChatModel) -> Graph:
    """The agent's graph on a model, saving its progress with the process's saver."""
    # ToolNode's own error handling stays off: with a wrapper, it hands every
    # error to its handler, whatever type the handler takes.
    tools = ToolNode(TOOLS, handle_tool_errors=False, wrap_tool_call=recorded_tool_call)
    graph = StateGraph(State, context_schema=RunContext)
    graph.add_node("agent", model_node(model.bind_tools(TOOLS)), retry_policy=RETRY)
    graph.add_node("tools", tools, retry_policy=RETRY)
    graph.add_node("remind", remind)
    graph.add_node("decided", decided)
    graph.add_node(
        "wait_for_supervisor", wait_for_supervisor, destinations=("agent", END)
    )
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", after_agent, ["tools", "remind"])
    graph.add_edge("remind", "agent")
    graph.add_edge("tools", "decided")
    graph.add_conditional_edges(
        "decided", after_decided, ["agent", "wait_for_supervisor", END]
    )
    return graph.compile(checkpointer=checkpoints.saver())


# Running it

TERMINAL = ("refunded", "declined", "escalated")


def context_of(request: dict[str, Any], model_name: str) -> RunContext:
    return RunContext(
        request_id=request["id"],
        order_id=request["order_id"],
        attempt=request["attempt"],
        model=model_name,
    )


def thread_of(request: dict[str, Any]) -> RunnableConfig:
    """The attempt's thread, named for the database's generation too, so a graph
    from before a reseeding is never taken up."""
    thread = f"{request['generation']}:{request['id']}:{request['attempt']}"
    return {"configurable": {"thread_id": thread}}


def answered(graph: Graph, config: RunnableConfig, answer: dict[str, Any]) -> bool:
    """Whether the graph has taken a supervisor's answer: a sign-off ends it, and
    a send-back moves it to the answer's revision."""
    saved = graph.get_state(config)
    if answer["kind"] == "signed_off":
        return not saved.next
    return saved.values.get("revision", 0) >= answer["revision"]


def deliver(
    graph: Graph, config: RunnableConfig, context: RunContext, answer: dict[str, Any]
) -> None:
    """Give the graph a supervisor's answer. A graph that stopped before it paused
    first finishes its saved work, which pauses it; it then gets the answer."""
    for _ in range(2):
        graph.invoke(Command(resume=answer), config, context=context, durability="sync")
        if answered(graph, config, answer):
            return


def unanswered_send_back(
    request: dict[str, Any], revision: int
) -> dict[str, Any] | None:
    """A send-back the backend recorded that the graph hasn't taken, as an answer."""
    sent = request["send_back"]
    if sent is None or sent["revision"] <= revision:
        return None
    return {"kind": "sent_back", "note": sent["note"], "revision": sent["revision"]}


def work(request: dict[str, Any], model: BaseChatModel, model_name: str) -> None:
    """Work a request's current attempt: start it, give it a send-back that never
    reached it, or carry it on from where it got to. A request that is finished
    is left as it is."""
    if request["state"] in TERMINAL:
        return
    graph = build(model)
    config = thread_of(request)
    context = context_of(request, model_name)
    saved = graph.get_state(config)
    if not saved.values:
        start = {
            "messages": [HumanMessage(f"Decide refund request {request['id']}.")],
            "revision": request["revision"],
        }
        graph.invoke(start, config, context=context, durability="sync")
    elif answer := unanswered_send_back(request, saved.values["revision"]):
        deliver(graph, config, context, answer)
    elif saved.next:
        graph.invoke(None, config, context=context, durability="sync")


def resume(
    request: dict[str, Any],
    answer: dict[str, Any],
    model: BaseChatModel,
    model_name: str,
) -> None:
    """Give a paused attempt a supervisor's answer: signed off, or sent back with a
    note and the new revision."""
    deliver(build(model), thread_of(request), context_of(request, model_name), answer)
