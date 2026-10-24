# The agent improving itself, with a person's approval

From the head of customer support at Acme Store.

<!-- An add-on brief. It builds on docs/addons/EVALS.md. Copy it to docs/IMPROVE.md to make it part of the build, then ask for a plan. -->

## Where we are

Evaluations score the agent's decisions against our own. The agent's instructions and model are fixed in code.

## What we need

- The agent's instructions, model and reasoning effort make up one configuration, kept in versions. Each version records what it changed from the one before, why, who proposed and approved it, and its held-out scores.
- A second agent, the improver, works in rounds that a supervisor starts:
  1. The round makes sure the current version has one evaluation on the evaluation set and two on the held-out set.
  2. The improver reads the results and proposes a new version with its reason, then waits for a supervisor to approve or reject it. A rejection's reason goes back to the improver, which may propose again.
  3. An approved version is evaluated once on the evaluation set and twice on the held-out set.
  4. Our rule keeps the version or rolls it back. It must meet our objectives on the held-out set, improve at least one measure by more than its noise, and make none worse by more than its tolerance.
- Each round has a spending limit covering the improver, its evaluations and the judge. Once the limit is spent, no new request starts in the round.

## Rules

- The improver can't change our objectives, the noise and tolerance, the spending limit, the models allowed, the approval limit, the labeled sets or the judge.
- Nothing it proposes takes effect until a supervisor approves it.
- One round is open at a time, and a supervisor can stop it. A round stopped before its verdict leaves the current version as it was.

## What the team needs to see

- The versions, each with its diff from the one before.
- Where a round has got to, and a proposal waiting with its change shown as a diff.
- The verdict and why, and the round's cost.

## Not for now

- The improver changing the agent's tools or graph: it changes only the configuration.
- Rounds that run on a schedule.

## Notes for the plan

The improver is LangChain's `create_agent` with `HumanInTheLoopMiddleware` for the supervisor's approval and `ModelCallLimitMiddleware` for its calls. The keep-or-roll-back rule is code in the backend, never the improver's call.
