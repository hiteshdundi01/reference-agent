# Process

## Setting up and running

- `uv sync` and `npm install` at the repo root install everything. They also install the git pre-commit hook and Playwright's browser.
- Copy `.env.example` to `.env` and fill it in.
- `npm run seed` rebuilds the database from `data/`.
- `npm run dev` starts the backend on port 8000, the agent on port 8080 and the dashboard, passing `.env` to the backend and the agent.

## The checks

`npm run check` runs every check but the end-to-end tests at once, each one's output shown in one piece, then the end-to-end tests on their own:

- **Python:** ruff (lint and format), pyright, and pytest with at least 80% coverage, across the machine's cores.
- **The server check:** the backend imports with only the `server` dependency group installed, in a temporary environment that leaves `.venv` alone.
- **The agent check:** the agent's app imports with only the `agent` dependency group installed, in the same way.
- **TypeScript:** Prettier, ESLint, tsc, and vitest with at least 80% coverage.
- **End to end:** Playwright tests against their own backend, dashboard and stand-ins, on their own ports.

The checks call no real model, reach no service outside the machine and never read `.env`. They do start servers on the machine itself:

- the tests use SQLite files of their own;
- a stub model stands in for every model;
- the e2e tests use a stand-in for the agent.

Installing (`uv sync`, `npm install`) needs the network. Once it has run, the checks don't.

The pre-commit hook formats the staged files, then runs the Python or TypeScript checks for the part that changed. GitHub Actions runs `npm run check` on every push and pull request, on Ubuntu, macOS and Windows (`.github/workflows/check.yml`).

## Planning

When asked to plan, as in "Please plan the work in `docs/<NAME>.md`", write the plan to `docs/PLAN_<NAME>.md` (`docs/PLAN.md` for `docs/SPEC.md`), in the shape of `docs/templates/PLAN.md`, and write no code.

- Start with the design: the modules, what each one is for and how they depend on each other. Check it against `docs/CODE_STANDARDS.md` before you write the phases.
- Describe the agent's instructions by their goals, never as a list of steps.
- For anything that moves through states, write the state machine as a table: from, operation and caller, to, and what is refused.
- Split the work into phases, usually 5 or 6, each building on the last.
- Give each phase detailed success criteria that you can verify yourself, each one a checkbox:
  - tests that pass;
  - commands and their output;
  - API calls and their responses;
  - pages you check in the browser with the Playwright MCP server.
- Then stop and wait until you are asked to implement the plan.

## Implementing

When asked to implement a plan, create a branch for it (`build/<name>`), then build every phase in order without stopping. For each phase:

1. Build it, with tests. While you work, run only the tests for the code you're changing, without coverage, for example `uv run pytest backend/tests/test_requests.py --no-cov`.
2. Check every success criterion and fix whatever fails. Then run `npm run check` and fix whatever fails.
3. Review the phase's changes as `docs/REVIEW_PROTOCOL.md` describes. Fix what the review finds, then run only the tests the fixes touch, plus `npm run e2e` if they change the dashboard or the API.
4. Tick off the phase's criteria in the plan, and update `docs/STATUS.md`, including its review log.
5. Commit without running `npm run check` again. The pre-commit hook reruns the checks; if it fails, fix the problem and commit again.

When the last phase is done, review the whole branch against `git merge-base main HEAD` in the same way; that review is always dual. Fix what it finds, run the tests the fixes touch, and commit. Then report the results, including what the reviews found and what you changed. The person merges the branch.

## Reviewing

The checks show that the code works, but not that it is fit to merge. Every change gets a review before it is committed, by GPT or Argon as `docs/REVIEW_PROTOCOL.md` and `review.config.yaml` say. Reviewing needs three tools besides the repo's own: the Codex CLI (`codex`), the Antigravity CLI (`agy`) and gitleaks (`brew install gitleaks`, or a release from its GitHub page). The checks need none of them: their tests use a stand-in for gitleaks. `node scripts/review-packet.mjs` builds the review's prompt and checks it for secrets. A finding you disagree with goes in your report with your reason; never skip one quietly.

## Rules

- Add tests with each change. Tests never call a real model; they use the stub model.
- Outside a plan, commit each change once you have checked and reviewed it, and run `npm run check` before you hand work over.
- Never use `git commit --no-verify`.
- Never lower a threshold, turn off a rule or exclude a file to get a green run. If a rule looks wrong, stop and ask.
- Keep `docs/STATUS.md` up to date.
- Never push.
- Everything must work on Windows, macOS and Linux: write `package.json` scripts as `uv run` commands, npm tools or `.mjs` files.
