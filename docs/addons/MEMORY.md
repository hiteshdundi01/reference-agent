# The agent remembering each customer

From the head of customer support at Acme Store.

<!-- An add-on brief. Copy it to docs/MEMORY.md to make it part of the build, then ask for a plan. -->

## Where we are

The agent reads a customer's earlier requests from the backend, but keeps no notes of its own.

## What we need

- When the agent's work on a request ends with a decision it recorded, the request and the decision are saved to that customer's memory. The customer's own words and evidence are never saved.
- On a later request, the agent can search what it remembers about that customer.
- Each customer's memories are used only for that customer's requests.

## Rules

- The backend's records still count for repeated requests (Section 7). Memory is the agent's notes, not the system of record.
- Nothing is saved for a request the security check escalated, and evaluations use no memory.
- The memory is reached through one module, the one place with its settings and its namespaces (`("customers", <customer id>)`).

## Not for now

- People reading or editing what the agent remembers.
- Memory of anything but customers.

## Notes for the plan

A LangGraph store passed at compile gives the graph its memory: an in-memory store in the tests, and a hosted one (such as AgentCore Memory, `docs/addons/AWS.md`) in production. A `remember` node, run in code after a decision, saves it; the model doesn't decide whether to.
