"""A stub model, so that no test calls a real model, and replies to script it."""

import itertools

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from backend.tests.moves import REASON

# What a provider reports for each reply.
USAGE = {"input_tokens": 1200, "output_tokens": 300, "total_tokens": 1500}
SECTION = "Section 3"
CALL_IDS = itertools.count()


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies, or raises a scripted error, and
    keeps the prompts it was sent."""

    prompts: list[list] = []

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.prompts.append(messages)
        return super()._generate(messages, stop, run_manager, **kwargs)


class Failing(Exception):
    """A scripted failure, as a model or a process might fail."""


def stub(*replies) -> StubModel:
    """A stub model giving these replies in turn; an exception among them is
    raised in its place."""

    def given():
        for reply in replies:
            if isinstance(reply, BaseException):
                raise reply
            yield reply

    return StubModel(messages=given(), prompts=[])


def says(text: str) -> AIMessage:
    return AIMessage(content=text, usage_metadata=USAGE)


def call(name: str, **args) -> AIMessage:
    """A reply that calls one tool, with an id of its own as a real model gives."""
    tool_call = {"name": name, "args": args, "id": f"call-{next(CALL_IDS)}"}
    return AIMessage(content="", tool_calls=[tool_call], usage_metadata=USAGE)


def approve(amount: float, section: str = SECTION, reason: str = REASON) -> AIMessage:
    return call("approve_refund", amount=amount, section=section, reason=reason)


def decline(
    section: str = "Section 4", reason: str = "The lamp was final sale."
) -> AIMessage:
    return call(
        "decline_or_escalate", decision="decline", section=section, reason=reason
    )


def escalate(
    section: str = "Section 6", reason: str = "This needs a person."
) -> AIMessage:
    return call(
        "decline_or_escalate", decision="escalate", section=section, reason=reason
    )


def reads(*names: str) -> list[AIMessage]:
    return [call(name) for name in names]
