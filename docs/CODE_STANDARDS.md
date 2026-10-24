# Code standards

## General

1. Keep it simple. Don't build for a need the documents don't state.
2. Comments only when the code can't say it: why, not what.
3. Be concise: a short README, plain English and no emojis.
4. IMPORTANT: avoid overly defensive code. Handle an exception only where there is something useful to do with it.
5. Use uv: ALWAYS `uv run`, NEVER `python` or `python3` directly.
6. TypeScript: strict mode, never `any`.

## Structure

7. **One way to do each thing.** Each service is reached through one module, which holds its address and settings, and nothing else reaches it:
   - the agent reaches the backend only through `agent/api.py`, on the one client in `agent/connection.py`;
   - the backend reaches the agent only through `backend/agent_service.py`;
   - the dashboard reaches the backend only through `dashboard/src/api.ts`, on `dashboard/src/connection.ts`;
   - the agent builds models only in `agent/models.py`;
   - the backend checks sign-ins only in `backend/auth.py`.

   Each API module has one function per backend operation, named after the operation. No other module builds a URL or sends a request.

8. **Each module has one job, and its name says what it is.** A module uses another through what that module is for, and never borrows its helpers. A helper two modules need goes in a module of its own. No circular imports. Tests follow the same rules: shared test helpers live in their own modules, never in another test file.
9. **Name a shared literal once.** A URL, an env var's name, a path, a status or a message used in more than one place is defined once, in the module that owns it. A literal used once stays where it is used.
10. **Use the framework's own way before writing your own:**
    - FastAPI: dependencies, models and `operation_id`s.
    - SQLAlchemy Core for the database. A move only one caller may make is a conditional update that checks its row count.
    - LangGraph: `StateGraph`, `ToolNode`, conditional edges, `RetryPolicy`, a checkpointer, and `interrupt()` with `Command(resume=...)` for a person's answer.
    - LangChain: `init_chat_model` for models, and `context_schema` with `ToolRuntime` for what a tool needs to know.
    - Pydantic: a discriminated union for payloads with variants.
    - React: hooks and shared components.

    Check the documentation for the installed version.

11. **A function does one job.** Split one that mixes levels of detail, such as setting up a run, driving the agent and recording the result.
12. **When you extend code, bring it up to these standards first.** Never copy a pattern they rule out.

## The API

13. Every operation has an `operation_id` and a one-line docstring. Operations tagged `agent`, the ones the agent's tools call, take no optional inputs, including inside nested models, because an optional field in a tool's schema invites a model to guess. Model variants as a discriminated union instead. `api_rules.py` checks all of this against the OpenAPI schema.
14. **The backend enforces every business rule, whatever the agent or the dashboard does.** The agent may be wrong, replayed or late. The backend refuses with a status and a reason that says what is wrong.

## The agent

15. **The agent's parts are kept apart:**
    - `connection.py` and `api.py` are the backend's API;
    - `models.py` builds models and reads their usage;
    - `tools.py` holds the tools and the context they read;
    - `harness.py` builds and runs the graph;
    - `checkpoints.py` keeps the graph's progress;
    - `entrypoint.py` is the agent's app.

    `test_boundaries.py` checks which module may import which.

16. **Tools take their ids from the run's context, never from the model:** the request, the order, the customer, the attempt and the revision. A refusal from the backend goes back to the model as the tool's result, so it can act on the reason.
17. **Instructions give the agent its goal, what it has to work from and what done looks like.** They never script its steps: it plans those itself. Anything that must always happen, or happen in a fixed order, is code.

## The dashboard

18. Pages read with `useLoad` and act with `useAction`, through `api.ts`. A page shows only what the backend's records say. It never works out a state for itself.
19. The look follows `docs/BRAND.md`, with colors and spacing as CSS variables, in light and dark mode.
