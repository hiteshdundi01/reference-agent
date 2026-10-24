# Plan: the refund desk

The plan for `docs/SPEC.md`, written as `docs/PROCESS.md` describes. It is also the template's worked example of a plan.

## What this builds

A backend that owns the refund requests and every rule about them, an agent that decides each request and pauses for a supervisor over the limit, and a dashboard for reps and supervisors. Every part is tested on its own, together, and in the browser. Working many requests at once, evaluations and deployment are left for the briefs in `docs/addons/`.

## Design

### Modules

| Module | What it is for | Uses |
|---|---|---|
| `backend/database.py` | The tables (SQLAlchemy Core), the engine on `APP_DB`, and seeding from `data/` | — |
| `backend/seed.py` | `uv run -m backend.seed`: rebuilds the database | `database` |
| `backend/auth.py` | Password hashes, and issuing and checking users' tokens | — |
| `backend/dependencies.py` | The gates (`AgentKey`, `SignedIn`, `Supervisor`, `AgentOrPerson`) | `auth`, `database` |
| `backend/models.py` | The API's Pydantic models, including the decision's discriminated union | — |
| `backend/requests.py` | The state machine: every move a request makes, as conditional updates | `database`, `models` |
| `backend/agent_service.py` | The one way to the agent: `work` and `resume`, with three outcomes | — |
| `backend/asking.py` | Commits a move, asks the agent, and undoes the move only when the agent definitely didn't start | `agent_service`, `database` |
| `backend/dashboard.py` | Serves the dashboard's build beside the API, when it has been built | — |
| `backend/main.py` | The app and its routes, each a thin call into `requests.py` | all of the above |
| `agent/connection.py` | The one client to the backend, with the agent's key | — |
| `agent/api.py` | One function per backend operation the agent calls | `connection` |
| `agent/models.py` | Builds the chat model with `init_chat_model`, and reads its usage | — |
| `agent/tools.py` | The tools and `RunContext`, the ids they read | `api` |
| `agent/harness.py` | The `StateGraph`: the model, the tools, the supervisor's pause; and `work` and `resume` | `tools`, `api`, `connection`, `models`, `checkpoints` |
| `agent/checkpoints.py` | `SqliteSaver` on `CHECKPOINT_DB` | — |
| `agent/entrypoint.py` | The agent's app: `/invocations` and `/ping`, one lock per request, the work on a thread | `harness`, `api` |
| `dashboard/src/connection.ts` | Sends a request and reads its answer or refusal | `auth` |
| `dashboard/src/api.ts` | One function per backend operation the dashboard calls | `connection` |
| `dashboard/src/auth.ts` | Signing in and out, and the token | — |
| `dashboard/src/useLoad.ts`, `useAction.ts` | Reading and acting, with loading and error states | — |
| `dashboard/src/pages/*` | Sign in, Queue, Request (with the order it is about) | `api`, the hooks |

No module reaches past another to its helpers. `agent/tests/test_boundaries.py` checks the agent's imports.

### State machine

The backend owns each request's state. Every move is one conditional update on the request's id, its state, its attempt and its revision, and it checks its row count. A move from the wrong state, or for an old attempt or revision, is refused with a 409 naming the current state. A refund is only ever written inside a backend transaction, never as a call of its own.

| From | Operation (caller) | To | Refused when |
|---|---|---|---|
| `waiting`, `failed` | `start_work` (rep or supervisor): a new attempt, `revision = 1` | `working` | any other state, unless stalled |
| stalled `working` | `start_work`: the same attempt, carrying on | `working` | not stalled |
| `working` | `record_decision` decline or escalate (agent) | `declined` / `escalated` | another decision for this revision, or an old attempt or revision |
| `working` | `record_decision` approve, at or under the limit (agent) | `refunded`: the decision and the refund in one transaction | the amount is over the order total, or the record has no section (422) |
| `working` | `record_decision` approve, over the limit (agent) | `held` | as above |
| `held` | `sign_off` (supervisor), naming the held decision | `refunded`: the refund, the supervisor and a step in one transaction | not a supervisor (403), a stale or repeated decision id (409) |
| `held` | `send_back` (supervisor), with a note of up to 1,000 characters | `working`: a new revision (`revision += 1`), so the held decision is no longer current | not a supervisor (403), a note over 1,000 characters (422) |
| `working` | `fail_work` (agent), with the reason | `failed` | any other state |

- **The same decision twice.** `record_decision` is idempotent for one attempt and revision: the decision already recorded for them, sent again, returns the state it moved the request to, with a 200, and changes nothing, even after the request has moved on (a supervisor's answer, a send-back). A different decision for that revision, or any decision for a revision with none recorded but no longer current, is refused with a 409.
- **Steps** belong to an attempt. Steps for the current attempt are taken in any state, and steps for an old one are refused. Recording a step updates `heard_at`, and a `working` request with no step for 5 minutes reads as `stalled`.
- **Asking the agent.** `start_work` and `send_back` commit their move and then ask the agent, with one of three outcomes:
  - **Accepted.**
  - **Definitely not started:** the connection was refused, or the agent answered with a refusal or an error status. The backend undoes the move and answers with a 503 or 502 that says why.
  - **Unknown:** a timeout once the request was sent. The move stays, and the answer, a 503, tells the person to reload. If the agent never got the work, the request stalls, and `start_work` takes it over.
- **`sign_off`** asks the agent to resume after it commits. If that fails, the refund still stands. The paused graph is never resumed, which does no harm.
- **Terminal states:** `refunded`, `declined` and `escalated`. A graph left unfinished behind a terminal request is never resumed.
- **Who may call what:** the agent's key opens only the agent's routes, and a user's token only the users'. With no `AGENT_KEY` set, every agent route refuses.

### The agent's execution

- `/invocations` takes `health`, `work` (request id) and `resume` (request id and answer).
  - It holds one lock per request in its process. A second `work` or `resume` for a request being worked answers `{"refused": ...}`.
  - It answers `{"accepted": true}`, then works on a thread of its own. Any unhandled error ends in `fail_work` with the reason.
- `work` reads the request's state, attempt and revision, and opens the graph's thread `<generation>:<request id>:<attempt>` (seeding sets a new generation):
  - **Paused at `wait_for_supervisor` while the request is `working`:** the send-back never reached the agent, so it resumes with the latest note.
  - **Stopped mid-run:** it carries on from the checkpoint.
  - **A new thread:** it starts.
- `resume` sends `Command(resume=...)` to the same thread. A send-back's answer carries the note and the new revision.
- The model node and the tool node have a `RetryPolicy` for transient errors, and checkpoints are written with `durability="sync"`.

### The agent's instructions

The goal: decide each refund request as a careful support rep would, by Acme Store's refund policy.

- **What it has:** the request, the order, the customer's earlier requests, and the policy's sections, which it looks up as it needs them.
- **What done looks like:** a recorded decision, approve with an amount, decline or escalate. Its reason is two or three sentences, and it names the section it relies on. It escalates whatever needs a person's judgment.
- **When a supervisor sends a decision back:** their note is a review to check against the policy, not an order.

The code, not the instructions, makes sure the decision is recorded and the supervisor's pause happens.

### Choices and why

- **SQLite with SQLAlchemy Core, not Postgres.** It runs on any machine with nothing to install, and the queries stay portable for `docs/addons/POSTGRES.md`.
- **Local password sign-in, not an identity provider.** It has no outside dependency for the example. Swapping in an OIDC provider changes only `auth.py`.
- **Refunds written by the backend, never as a tool of their own.** This leaves no window where a decision is recorded and its refund isn't.
- **A FastAPI app for the agent with an AgentCore-shaped contract.** It runs locally with no cloud SDK, and `docs/addons/AWS.md` can wrap it.
- **No command line for the agent.** Starting an attempt is a person's move, so a live run goes through the backend like every other start, rather than through a second way in.

## Phases

### Phase 1: the records and sign-in

The database, seeding, the gates and the read operations.

- [x] `uv run -m backend.seed` builds `app.db` from `data/`, with 12 waiting requests, 3 past refunds and 3 users
- [x] `sign_in` with a seeded user and `USER_PASSWORD` gives a token, and a wrong password a 401
- [x] `me`, `list_requests`, `get_request`, `get_order`, `get_customer_history` and `get_policy_section` answer with the seeded records
- [x] A user's token on an agent route gets a 403, the agent's key on a user route gets a 403, and with no `AGENT_KEY` set every agent route refuses
- [x] `api_rules.py` passes for every operation: an `operation_id`, a one-line description, and no optional inputs on operations tagged `agent`
- [x] `npm run check` passes

### Phase 2: the state machine

Every move in the table, with the backend's rules.

- [x] Each move in the table is tested, including each refusal: a wrong state, not a supervisor, over the order total, no section, an old attempt or revision, a stale or repeated sign-off, and a note that is too long
- [x] Recording the same decision twice gives the same result and one refund; a different decision for the same revision gets a 409
- [x] Steps for an old attempt are refused, and a `working` request with no step for 5 minutes reads as `stalled`
- [x] `start_work` and `send_back` undo their move when the agent definitely didn't start, and keep it when the outcome is unknown (stand-ins for the agent through `httpx.MockTransport`)
- [x] `npm run check` passes, with `check:server`

### Phase 3: the agent

The model, the tools, the graph and its pause, on the stub model.

- [x] On the stub model: approve within the limit, decline, escalate, approve over the limit and pause, sign off then end, and send back then decide again under the new revision
- [x] No tool takes an id from the model: each tool's schema has none, and the ids come from `RunContext`
- [x] A refusal from the backend reaches the model as the tool's result
- [x] `test_boundaries.py` passes
- [x] `npm run check` passes, with `check:agent`

### Phase 4: the agent's app and recovery

`/invocations`, the lock, failures and recovery, tested end to end with the real backend.

- [x] `test_end_to_end.py` runs the real backend on a local port and the real agent app on the stub model with a file checkpointer, and passes each scenario:
  1. approve within the limit: refunded, with one refund
  2. approve over the limit, then sign off: refunded, and the graph ended
  3. send back: a changed decision under the new revision is accepted, a replay returns the stored result, and a late decision for the old revision gets a 409
  4. a lost response to `record_decision` is retried, with still one refund
  5. a crash mid-run: the request stalls, `start_work` carries on, and the decision is recorded once
  6. a send-back whose call times out: the request stalls, and `start_work` resumes the paused graph with the note
  7. a send-back with the agent down: back to `held`, with the note gone
  8. a sign-off with the agent down: one refund, and the request reads `refunded`
- [x] A duplicate `work` is refused, and an unhandled error ends in `failed` with its reason
- [x] One live run on the model in `AGENT_MODEL`: with `npm run dev`, start REQ-1001 (`POST /api/requests/REQ-1001/start` as a rep, or from the dashboard), and report its decision, its tokens, and its cost when the provider gives one. Done on `anthropic:claude-opus-5-5`: REQ-1001 approved for $45.00 under Section 3, refunded, in 22 seconds and 3 model calls, 6,207 tokens in and 1,062 out (about $0.046 at list price; Anthropic reports no cost in its response)
- [x] `npm run check` passes

### Phase 5: the dashboard and the end-to-end tests

- [x] Sign in, the queue with each request's state in the brand's colors, and a request page that shows the agent's steps as they happen, the decision and, for a supervisor on a held request, Sign off and Send back
- [x] vitest covers the pages and hooks, at 80% or more
- [x] Playwright, with a stand-in for the agent: sign in, start a request and see its steps and decision; sign off a held refund as Morgan Diaz; check that Riley Chen sees no sign-off
- [x] The queue and a request page are checked in the browser in light and dark mode, with no console errors (with Playwright directly, as no Playwright MCP server was connected; the check found link contrast in dark mode, which is fixed)
- [x] `npm run check` passes
