# The refund desk

From the head of customer support at Acme Store.

<!-- This is the example product's spec. A new product replaces this file with its own spec, written in the same way: the customer's needs in the customer's words (docs/ADAPTING.md). -->

## How refunds work today

Acme Store sells home goods online. When a customer wants their money back, they send a refund request: which order, how much, and why. Our support reps work through the requests by hand. For each one, a rep:

1. reads the customer's reason, the order and the customer's earlier requests;
2. checks the refund policy;
3. approves a refund for an amount, declines it, or escalates it to a supervisor when it needs someone's judgment.

Refunds over $200 need a supervisor's sign-off.

## What we want

We want an AI agent to work each request the way a good rep does. For each request it should:

- read the request, the order, the customer's earlier requests and the sections of the refund policy it needs;
- approve with an amount, decline, or escalate;
- explain the decision in two or three sentences, naming the section of the policy it relied on.

A rep starts the agent on a request from the dashboard and watches its steps as it works.

## Rules

- Decisions follow `data/refund_policy.md`.
- A refund can never be more than what the customer paid for the order.
- A refund over the approval limit, $200 to start with and a setting, waits for a supervisor.
  - The agent can approve such a refund, but nothing is paid until a supervisor signs it off.
  - A supervisor either signs it off, which issues the refund at once, or sends it back to the agent with a note of up to 1,000 characters saying what to look at again.
  - The agent reads the note as a supervisor's review, checks it against the policy like everything else, and decides again.
- Every decision is recorded with the decision, the amount for an approval, the section of the policy relied on, the reason, who or what made it, and when. Our system refuses a decision that falls short and says what is missing.
- No refund is ever issued twice, even if a step runs again after a restart.
- Reps and supervisors sign in with their email and password. Every page needs a signed-in person, and our system checks who they are on every action.
- Only a supervisor can sign off or send back a held refund. Anyone else is told they can't, and why.
- The agent identifies itself with its own key on every request it makes to our system. The key never stands in for a person.
- Work survives a restart.
  - If the agent stops partway through a request, starting it again carries on from where it got to.
  - A request the agent hasn't spoken of for five minutes counts as stalled, and a rep can start it again.
  - If the agent fails, the request says so, with why, and a rep can start it again.
- Amounts are in US dollars.

## What the team needs to see

- The queue: every request with its customer, its amount and where it stands. The states are waiting, working, stalled, held for a supervisor, refunded, declined, escalated and failed.
- Each request in full: the customer's reason, the order, the agent's steps as they happen, and the decision with its reason and policy section.
- For a held refund: the agent's reason, and for a supervisor, Sign off and Send back.

## Our records

Everything is in `data/`, described in `data/README.md`: the customers, their orders, the refund requests, our reps and supervisors, and the refund policy.

## Not for now

- Customers making requests themselves. The requests are already in our system.
- Partial refunds of single items, store credit or exchanges.
- Messages to customers.
- Real payments: issuing a refund records it.
- Working many requests at once, or evaluating the agent against a labeled set (see `docs/addons/`).
