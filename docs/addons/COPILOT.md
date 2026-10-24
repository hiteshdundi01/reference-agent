# A copilot for the support team

From the head of customer support at Acme Store.

<!-- An add-on brief. Copy it to docs/COPILOT.md to make it part of the build, then ask for a plan. -->

## Where we are

Reps and supervisors use the dashboard's pages to find requests, start the agent and answer held refunds.

## What we need

- A chat in a sidebar on every page. A person asks in plain English, and it answers and does the work for them.
- It works as the person who asked, with their own sign-in, so it can see and do exactly what they can. It never uses the agent's key, and a rep can't sign off through it.
- It looks things up in our records, starts the agent on a request, and sends a held decision back with a note.
- For a sign-off, it shows a card with the request, the customer, the amount and the agent's reason, all from our records. Nothing is refunded until the supervisor presses Sign off and refund on that card.
- Each step it takes shows as a card in the sidebar as it happens. Conversations are kept, each its person's alone.

## Rules

- What must always happen is code: the check of the sign-in, the pause before a sign-off, and the answer after a Cancel.
- A confirmation is bound to the card that was shown. An answer from an old tab, or for a decision that has changed since, is taken as a Cancel.
- Tool calls run one at a time.

## Not for now

- Streaming answers word by word.
- Sharing, renaming or deleting conversations.

## Notes for the plan

The copilot is an agent of its own, beside the refund agent. It shares only the modules both need, and test_boundaries.py checks that. It is a hand-written `StateGraph`: the model, a `ToolNode`, a node that checks the sign-off in code, and a node of its own for the `interrupt()`.
