# Starting a new product from this template

The template is a working product, the Acme refund desk, plus the playbook that built it. A new product keeps the playbook and the patterns, and replaces the example. Work through these steps in order, with your coding agent, and commit after each.

## 1. Make the repo yours

- Copy the repo without its history: `git clone --depth 1 <template> <new name>`, `rm -rf .git`, then `git init -b main` and commit everything as the first commit.
- Rename the project in `pyproject.toml` (`name`) and `package.json` (`name`).
- Replace the product's name in `AGENTS.md`'s first lines, `README.md`, `dashboard/index.html`, `backend/main.py` and `agent/entrypoint.py` (each app's `title`).

## 2. Write your spec

- Replace `docs/SPEC.md` with your customer's spec, in their words, in the shape `docs/templates/BRIEF.md` gives a brief: how things work today, what they want, the rules, what the team needs to see, our records, and not for now.
- Replace `docs/BRAND.md`'s palette, fonts and mark, and keep its rules.
- Rewrite `docs/TECH_STACK.md` and `docs/CODE_STANDARDS.md` where your product differs. Keep the rules on one way to do each thing, one job for each module, the framework's way, agent instructions as goals, and the backend enforcing every rule.

## 3. Replace the example's data

- Replace `data/` with your business's seed data, and `data/README.md` with what each file is.
- Never put a real customer's data or a secret in `data/`.

## 4. Plan the first build

- Delete `docs/PLAN.md`, then ask your coding agent: "Please plan the pilot from `docs/SPEC.md`". It writes a new `docs/PLAN.md` as `docs/PROCESS.md` describes: the modules, the state machine as a table, the agent's instructions as goals, and 5 or 6 phases with checkbox criteria.
- Review the plan. Then ask: "Please implement the plan for the pilot".
- The example's code is there to read while the new plan is built. Each phase replaces the part of it the plan covers: the backend's records and moves, the agent's tools and graph, and the dashboard's pages. Delete what the new product doesn't use; don't leave the example's modules alongside your own.

## 5. Keep the review set up

- In `review.config.yaml`, update `mvp_dual` and `high_stakes` so that they name your modules that handle sign-in, permissions, money, safety, secrets and the agent's harness. The globs must match real files.
- Set `owner`, and add the approvals that stay human to `human_approvals`, such as a domain expert's review of the agent's instructions.
- Keep `tier: mvp` while the product is internal. Switch to `tier: production` before the first real user, real personal data or any environment outsiders can reach, as `docs/REVIEW_PROTOCOL.md` §0 says.

## 6. Add capabilities as you need them

`docs/addons/` holds briefs for capabilities most products need later:

| Brief | What it adds |
|---|---|
| `SWARM.md` | Many items worked at once by a dispatcher with no model |
| `EVALS.md` | Labeled sets, a held-out set, scoring and a judge |
| `IMPROVE.md` | Versioned configuration and an improver a person approves |
| `SECURE.md` | A check for hidden instructions, secrets and an identity provider |
| `CONTEXT.md` | An MCP context layer and one route to the agent's tools |
| `MEMORY.md` | The agent's memory of each customer |
| `COPILOT.md` | A chat that works as the signed-in person |
| `OBSERVABILITY.md` | Tracing and cost |
| `POSTGRES.md` | Postgres in place of SQLite |
| `AWS.md` | The backend on Lambda and the agent on AgentCore Runtime |

Rewrite a brief in your customer's words, copy it to `docs/`, and ask for a plan, as for any brief.
