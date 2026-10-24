"""Phase 3: the tools take no ids from the model, and decisions name the model."""

import pytest
from langchain_core.messages import AIMessage

from agent import models
from agent.tests.stubs import USAGE
from agent.tools import TOOLS

# What the model may give a tool. Every id comes from the run's context.
MODEL_INPUTS = {"number", "amount", "section", "reason", "decision"}
IDS = {"request_id", "order_id", "customer_id", "attempt", "revision", "decision_id"}


@pytest.mark.parametrize("tool", TOOLS, ids=lambda tool: tool.name)
def test_no_tool_takes_an_id_from_the_model(tool):
    inputs = set(tool.tool_call_schema.model_json_schema()["properties"])
    assert inputs <= MODEL_INPUTS
    assert not inputs & IDS


@pytest.mark.parametrize("tool", TOOLS, ids=lambda tool: tool.name)
def test_no_tool_has_an_optional_input(tool):
    schema = tool.tool_call_schema.model_json_schema()
    assert set(schema["properties"]) == set(schema.get("required", []))


def test_usage_names_tokens_and_a_reported_cost():
    reply = AIMessage(
        content="",
        usage_metadata=USAGE,
        response_metadata={"token_usage": {"cost": 0.0042}},
    )
    assert models.usage_of(reply) == "1,200 tokens in, 300 out, $0.0042"
    assert models.usage_of(AIMessage(content="", usage_metadata=USAGE)).endswith(
        "300 out"
    )
    assert models.usage_of(AIMessage(content="")) == "usage not reported"


def test_the_model_must_be_named(monkeypatch):
    monkeypatch.delenv("AGENT_MODEL")
    with pytest.raises(RuntimeError, match="AGENT_MODEL is missing"):
        models.chat_model()


def test_an_anthropic_model_names_its_workspace_when_one_is_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_WORKSPACE_ID", "wrkspc_test")
    assert models.provider_settings("anthropic:claude-opus-5-5") == {
        "default_headers": {"anthropic-workspace-id": "wrkspc_test"}
    }
    assert models.provider_settings("openai:some-model") == {}


def test_with_no_workspace_set_nothing_is_added():
    assert models.provider_settings("anthropic:claude-opus-5-5") == {}
