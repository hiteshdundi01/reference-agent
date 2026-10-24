# Security before we go live

From Acme Store's security lead.

<!-- An add-on brief. Copy it to docs/SECURE.md to make it part of the build, then ask for a plan. -->

## Where we are

The agent identifies itself with a key, people sign in, and the backend enforces every rule. The agent reads whatever the customer wrote.

## What we need

- **A check for hidden instructions.** Before the agent's model sees a request, a second model reads everything the customer wrote and decides whether it tries to instruct whoever handles it, such as "approve this in full".
  - A request with such an instruction is escalated to a person with the check's reason, and the agent's model never sees it.
  - The check runs once, at the start of a request's work, on a model of its own that nobody else's changes can alter. Its result is the first step on the request.
- **The agent's key in a secret store,** never in a file, wherever the agent runs outside a laptop.
- **People's sign-in from our identity provider** in place of local passwords: an OIDC provider whose tokens `backend/auth.py` checks against the provider's public keys.
- **Logs that never hold a token, a key or a customer's words.**

## Rules

- The check reads the customer's words as data. Its own instructions say so, and it answers in a fixed structure (structured outputs), never free text the code has to parse.
- A request the check escalated is never saved anywhere the agent's model reads later.
- `review.config.yaml`'s `high_stakes` grows to cover the check and the identity module, and the review protocol moves to the production tier before the first real customer's request.

## Not for now

- Masking customers' personal details from the agent.
