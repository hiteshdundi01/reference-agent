# The business data

The backend is seeded from these files by `npm run seed`. They are the example product's data; a new product replaces them.

- `customers.json`: Acme Store's customers, each with an id, name, email and the date they joined.
- `orders.json`: their orders. Each order has its items (price, quantity and whether it is final sale), shipping, the total paid, the expected and actual delivery dates, and the carrier's status (`delivered`, `lost` or `in_transit`).
- `requests.json`: the refund requests waiting in the queue. Each request has the order, when it was submitted, the amount asked for, the customer's reason and the evidence it came with (`none`, `photo` or `carrier_report`).
- `past_refunds.json`: earlier requests that were refunded, which make up a customer's history. They are seeded as refunded, decided by a support rep.
- `users.json`: the support team, each with the role `rep` or `supervisor`. All of them sign in with `USER_PASSWORD` from `.env`.
- `settings.json`: the approval limit in US dollars, above which a refund waits for a supervisor.
- `refund_policy.md`: the policy the agent decides by, in numbered sections, with its version in the front matter.
