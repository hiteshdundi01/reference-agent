# Reference agent

[![check](https://github.com/hiteshdundi01/reference-agent/actions/workflows/check.yml/badge.svg)](https://github.com/hiteshdundi01/reference-agent/actions/workflows/check.yml)

A template for building an end-to-end AI agent product with a coding agent, and a small working example of one: the Acme refund desk, where an agent decides customers' refund requests by a policy and a supervisor signs off the large ones.

It is for developers who build agent products with a coding agent such as Claude Code, and want a starting point that already holds a backend, an agent, a dashboard, the tests that hold them together, and a written way of working.

- **The playbook** in `docs/` says how to plan, build, check and review the work. A coding agent starts at `AGENTS.md`.
- **The example** is a FastAPI backend that owns every rule, a LangGraph agent with a supervisor's pause and durable progress, a React dashboard, and tests that run the whole thing on one machine.
- **Add-on briefs** in `docs/addons/` describe capabilities to add later: a swarm, evals, self-improvement, a context layer, memory, a copilot, security, observability, Postgres and AWS.

## What you need

- [uv](https://docs.astral.sh/uv/), which installs Python 3.13 for you
- Node 22 or later
- A key for the model the agent runs on, such as an Anthropic key, to run the agent for real. The checks don't need one.

The review process in `docs/REVIEW_PROTOCOL.md` also uses the Codex CLI, the Antigravity CLI and gitleaks. You need them only to review changes, not to run or check the example.

## Running the example

```bash
uv sync
npm install
cp .env.example .env
```

Then fill in `.env`:

- `AGENT_MODEL` and the provider's key, such as `ANTHROPIC_API_KEY`;
- `AGENT_KEY` and `AUTH_SECRET`, each a random value of its own, made with `uv run python -c "import secrets; print(secrets.token_urlsafe(32))"`;
- `USER_PASSWORD`, the password every seeded rep and supervisor signs in with.

```bash
npm run seed
npm run dev
```

Open the dashboard at the address Vite prints, and sign in as `riley.chen@acme.example` (a rep) or `morgan.diaz@acme.example` (a supervisor), with your `USER_PASSWORD`.

`npm run check` runs every check: lint, types, unit and integration tests, and the browser tests. It calls no real model and never reads `.env`. `docs/STATUS.md` says what is built and how to run it.

## Starting a new product

Follow `docs/ADAPTING.md`: make the repo yours, write your spec, replace the example's data, then have your coding agent plan and build the first version as `docs/PROCESS.md` describes.

## License

MIT. See `LICENSE`.
