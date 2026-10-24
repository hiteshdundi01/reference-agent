"""The one place the agent's chat model is made, from AGENT_MODEL as
"provider:model", and its usage read."""

import os
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage

AGENT_MODEL = "AGENT_MODEL"
ANTHROPIC_WORKSPACE_ID = "ANTHROPIC_WORKSPACE_ID"
MISSING_MODEL = 'AGENT_MODEL is missing. Add it to .env as "provider:model"'


def model_name() -> str:
    name = os.getenv(AGENT_MODEL)
    if not name:
        raise RuntimeError(MISSING_MODEL)
    return name


def provider_settings(name: str) -> dict[str, Any]:
    """What a provider needs beyond its key: an Anthropic key that isn't scoped
    to a workspace names the workspace in a header."""
    workspace = os.getenv(ANTHROPIC_WORKSPACE_ID)
    if name.startswith("anthropic:") and workspace:
        return {"default_headers": {"anthropic-workspace-id": workspace}}
    return {}


def chat_model() -> BaseChatModel:
    name = model_name()
    return init_chat_model(name, **provider_settings(name))


def usage_of(reply: AIMessage) -> str:
    """A reply's tokens, and its cost when the provider reports one."""
    usage = reply.usage_metadata
    if usage is None:
        return "usage not reported"
    words = f"{usage['input_tokens']:,} tokens in, {usage['output_tokens']:,} out"
    cost = reply.response_metadata.get("token_usage", {}).get("cost")
    return f"{words}, ${cost:.4f}" if cost is not None else words
