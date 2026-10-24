# Seeing what the agent did and what it cost

From Acme Store's engineering lead.

<!-- An add-on brief. Copy it to docs/OBSERVABILITY.md to make it part of the build, then ask for a plan. -->

## Where we are

Every step is recorded on its request, with each model reply's tokens, and its cost when the provider reports one.

## What we need

- Every run of the agent's graph traced in one place (Langfuse, or an OpenTelemetry backend), in a session named after the request and its attempt.
- The cost of every model call, from the provider's report where there is one, or else from a price table kept in one module and dated.
- A page or a query that answers: what did requests cost this week, by model; which requests took longest; and which failed, and why.

## Rules

- Traces never hold a sign-in token, a key, or a customer's email address.
- Tracing is off in the tests, and the checks never reach the tracing service.
- The price table names the date its prices were checked, and the model IDs it covers.

## Not for now

- Alerts and on-call.
- Dashboards beyond the one page or query above.
