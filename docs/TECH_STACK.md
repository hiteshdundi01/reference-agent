# Tech stack

## The parts

- **`backend/`:** FastAPI with SQLAlchemy Core on SQLite, at the file `APP_DB` names (`app.db` by default).
  - Queries are written in SQLAlchemy Core and kept free of SQLite-only features, so moving to Postgres is a change of connection (`docs/addons/POSTGRES.md`).
  - The backend owns every record and every business rule. Each request moves through the state machine in `docs/PLAN.md` by conditional updates.
  - Every refusal answers `{"detail": "..."}` with one line of text, validation errors included (`main.py` formats them without echoing what was sent), so the agent can hand any refusal to its model as it is.
  - Every route but `health` and `sign_in` has one gate, in `dependencies.py`:
    - `AgentKey` needs the agent's key in an `X-API-Key` header, compared with `AGENT_KEY` by `secrets.compare_digest`;
    - `SignedIn` needs a user's token;
    - `Supervisor` needs a signed-in supervisor;
    - `AgentOrPerson` takes either, for the reads both make.

    The key never stands in for a user, and a user's token never opens an agent route. With no `AGENT_KEY` set, every route that needs it refuses.

  - **Sign-in:** `auth.py` hashes passwords with argon2 (`pwdlib`) and issues and checks short-lived HS256 tokens signed with `AUTH_SECRET` (PyJWT). Users are seeded from `data/users.json`, all with the password in `USER_PASSWORD`. A move to an OIDC provider (Supabase Auth, Cognito, Auth0 and others) replaces what `auth.py` does inside and nothing else.
  - **Asking the agent:** `agent_service.py` asks the agent to work or resume a request with one JSON payload per operation, posted to `/invocations` at `AGENT_URL` (`http://127.0.0.1:8080` by default) with the key as `Authorization: Bearer <key>`. Each answer is one of three outcomes: accepted; definitely not started; or unknown, after a timeout once the request was sent. `asking.py` commits the move first, then asks, and undoes the move only when the agent definitely didn't start.
- **`agent/`:** a LangGraph agent served by its own FastAPI app.
  - `connection.py` holds the one client to the backend, at `APP_API` (`http://127.0.0.1:8000` by default), sending `AGENT_KEY` with every request.
  - `models.py` builds each model with LangChain's `init_chat_model` from `AGENT_MODEL`, written as `"provider:model"`. It reads each reply's input and output tokens from `usage_metadata`, and its cost only when the provider reports one.
  - `harness.py` builds a hand-written `StateGraph`: the model, a `ToolNode` whose `wrap_tool_call` records each step and hands the backend's refusals back to the model, and `wait_for_supervisor`, which pauses with `interrupt()`. Only transport errors on the way to the backend are retried, by `RetryPolicy`; model providers' clients retry their own.
  - `checkpoints.py` keeps the graph's progress with `SqliteSaver` at `CHECKPOINT_DB` (`checkpoints.db` by default), with `durability="sync"`. Each attempt is a thread named `<generation>:<request>:<attempt>`; seeding sets a new generation, so a graph from before a reseeding is never taken up.
  - `entrypoint.py` serves `POST /invocations` and `GET /ping`.
    - It reads each payload with a Pydantic discriminated union on `operation`, with no extra inputs; a 400 says what is wrong.
    - It answers `{"accepted": true}` at once and works on a thread of its own, or answers `{"refused": "..."}`.
    - This is the shape of Amazon Bedrock AgentCore Runtime's contract, so `docs/addons/AWS.md` can swap the app's wrapper and leave the harness alone.
- **`dashboard/`:** React, Vite and TypeScript, with React Router and `lucide-react` icons.
  - In development, Vite sends `/api` to the backend at `APP_API`. In production, the backend serves the built dashboard.
  - The signed-in user's token is kept in `sessionStorage` by `auth.ts`.
  - Pages read with `useLoad`, which reads again on a timer while the agent works, and act with `useAction`. The fonts are bundled from the `@fontsource-variable` packages.
- **`e2e/`:** Playwright tests.
  - They start their own backend on a SQLite file of its own, the dashboard, and a stand-in for the agent. The stand-in answers `/invocations` and plays a scripted decision through the backend's API with the key.
  - They run on ports of their own, so they never touch what `npm run dev` started.
- **`data/`:** the business data the backend is seeded from, described in `data/README.md`.

## Models

Every model comes from `init_chat_model`, so the provider is a setting. The `agent` dependency group ships two provider packages:

- `langchain-anthropic`, for `anthropic:<model>`;
- `langchain-openai`, for `openai:<model>`, and for any endpoint that speaks OpenAI's API, such as OpenRouter, set through `OPENAI_BASE_URL`.

A provider's own settings beyond its key are made in `models.py` too: with `ANTHROPIC_WORKSPACE_ID` set, an Anthropic model sends it as the `anthropic-workspace-id` header, which a key not scoped to a workspace needs.

To use another provider, add its LangChain package to the `agent` group (for example `uv add --group agent langchain-google-genai`), set `AGENT_MODEL` and the provider's key, and run `npm run check:agent`.

## Python and Node

- **Python:** 3.13 with uv, all in the root `pyproject.toml`. Each deployable has a dependency group: `server` for the backend and `agent` for the agent, plus `dev`. `uv sync` installs them all, and `npm run check:server` and `npm run check:agent` check that each deployable imports with its group alone.
- **Node:** 22 or later. Its tools (Vite, Vitest, ESLint, Prettier, Playwright, pyright and lefthook) are dev dependencies.

## Settings

`.env`, which never goes in git, holds:

- `AGENT_MODEL` and the provider's key, such as `ANTHROPIC_API_KEY`;
- `AGENT_KEY`, the agent's API key, which the backend and the agent share;
- `AUTH_SECRET`, which signs users' tokens;
- `USER_PASSWORD`, the seeded users' password;
- optionally `APP_DB`, `CHECKPOINT_DB`, `AGENT_URL` and `APP_API`.

`.env.example` lists them all.
