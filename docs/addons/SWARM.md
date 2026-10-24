# Working the queue on its own

From the head of customer support at Acme Store.

<!-- An add-on brief. Copy it to docs/SWARM.md to make it part of the build, then ask for a plan. -->

## Where we are

A rep starts the agent on one request at a time. Each request is a graph of its own with its progress saved, and the backend owns every request's state.

## What we need

- A rep starts a dispatch from the queue page, choosing how many requests are worked at once, from 1 to 25. A dispatch works every waiting request, every failed one, and every stalled one, oldest first.
- Code chooses the requests and keeps track of the dispatch, with no model. Each request gets an agent of its own, from a clean start, which reports back in one line: the decision and amount, or what went wrong.
- The backend keeps one dispatch going at a time. Asking for a second while one is going says what is going.
- One bad request never stops a dispatch. A request that hits a rate limit or a timeout waits and carries on as the same attempt. One that fails with any other error is tried once more from the start, and one that fails twice is left for a person.
- While a dispatch works, the agent tells the backend every minute that it is still going. A dispatch the backend hasn't heard of for five minutes counts as stopped, and the next one can start.
- When a dispatch ends, its summary is built from the backend's records, with no model writing it: how many were refunded, declined, escalated and held, and which were left for a person.
- The tokens and cost of every model call, and the time spent on each request, are recorded with the dispatch.

## Rules

- No request is ever decided or refunded twice, even when a dispatch is stopped and started again.
- Everything in `docs/PLAN.md`'s state machine still holds for each request in a dispatch.

## What the team needs to see

- On the queue page: Start a dispatch, with how many at once, and the latest dispatch with each of its requests, where each stands, and its cost and time.
- The summary when it ends.

## Not for now

- Scheduling dispatches.
- Priorities among requests.

## Notes for the plan

LangGraph's `Send` with `max_concurrency` fans the requests out; a `RetryPolicy` on the node that works a request handles rate limits and timeouts. A one-row `locks` table, updated as a start's first write, keeps one dispatch going at a time.
