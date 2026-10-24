# Status

<!-- Kept up to date as each phase is built (docs/PROCESS.md). A new product starts this file again from its own plan. -->

The example product, the Acme refund desk, is built: every phase of `docs/PLAN.md` is done and ticked.

- Phases 1 and 2: the records, sign-in, the gates and every move of the state machine.
- Phases 3 and 4: the agent's graph, its tools, the supervisor's pause, the agent's app and recovery, tested end to end with both apps on real ports, and one live run on a real model.
- Phase 5: the dashboard, and Playwright tests against the real backend and a stand-in for the agent.

## Running it

- `uv sync` and `npm install` install everything, including the pre-commit hook and Playwright's browser.
- `cp .env.example .env`, then fill it in.
- `npm run seed` builds `app.db`; `npm run dev` starts the backend, the agent and the dashboard. Sign in as `riley.chen@acme.example` (a rep) or `morgan.diaz@acme.example` (a supervisor) with `USER_PASSWORD`.
- `npm run check` runs every check.

## Known gaps

- A sign-off whose call to resume the agent fails leaves the refund issued and the agent's graph paused. The request reads `refunded`, and the paused graph is never resumed. This is deliberate and does no harm.
- A graph left unfinished behind a request that reached a terminal state (refunded, declined, escalated), for example by a crash right after its decision was recorded, is never resumed. This is deliberate.

## Review log

One line per review, in the MVP tier's format (`docs/REVIEW_PROTOCOL.md`): the unit, the reviewers and their sessions, the verdicts by round, and any open notes. The first row shows the shape; replace it with the first real review.

| Unit | Reviewers (session) | Verdicts | Notes |
| --- | --- | --- | --- |
| Phase 1 (example) | GPT-6.1-Sol (`<session id>`) and Gemini 4 Argon (`<conversation id>`), dual because of `backend/auth.py` | GPT: BLOCK, PASS. Argon: PASS. | What the blockers were and how each was fixed. No open notes. |
