# Checking the agent against our own decisions

From the head of customer support at Acme Store.

<!-- An add-on brief. Copy it to docs/EVALS.md to make it part of the build, then ask for a plan. -->

## Where we are

The agent decides refund requests, but nothing measures how often it decides as our best reps would.

## What we need

- Two labeled sets of requests, each with our reps' decision, amount and reason for every request: an evaluation set, to learn from, and a held-out set, which only scores changes.
- An evaluation works copies of one set through the same agent, whole or a tiny subset of five. The copies never show in the queue, nobody can sign them off, and an approval held for a supervisor counts as finished.
- Each evaluation is scored with our measures:
  - how often the decision matches our rep's;
  - how often the amount does too, within a dollar;
  - the cost of the mistakes: a wrongful decline at $150, a wrongful approval at its amount, and a needless escalation at $10;
  - the share decided without a person;
  - the model cost and time for each request;
  - the time for the whole run.
- A judge model grades each explanation against our rep's reason, A to F.
- A scoreboard lists the evaluations, newest first, each opening to its requests beside our reps' decisions, with the misses easy to spot.

## Rules

- The agent never sees the labeled decisions. Only the scoring reads them.
- Nothing a person or the agent can call returns the held-out set's decisions.
- The tests never call the judge; they use a stand-in.

## Not for now

- Evaluations on a schedule.
- Comparing two models side by side in one run.

## Notes for the plan

Keep the answer keys in `data/evals/` and list that folder under `review.config.yaml → exclude_paths.sealed`, so no review prompt ever carries them. Add a process rule that a coding agent doesn't open `data/evals/` unless it is asked to.
