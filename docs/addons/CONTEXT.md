# A context layer the agent looks things up in

From Acme Store's head of data governance.

<!-- An add-on brief. Copy it to docs/CONTEXT.md to make it part of the build, then ask for a plan. -->

## Where we are

The agent reads the policy one section at a time from the backend, and knows nothing else about the business.

## What we need

- Our data team's files become a context layer of their own: an MCP server, separate from the backend, that the agent reads and never writes. It holds:
  - the refund policy;
  - a glossary of the terms it defines;
  - what each field of a request and an order means;
  - the rules support applies to every request;
  - facts from outside Acme Store, such as carrier delays.
- Every answer names the file it came from, with that file's owner and review date, and the request page lists everything the agent looked up, once each, grouped by file.
- The agent's lookups and its calls to the backend take one route, chosen when its run is built: straight to each service on a laptop, or through a gateway in production.

## Rules

- The context layer is read-only, and nobody but our data team changes its files.
- MCP tools are called only through one module, and each route is one module, both what a shared protocol says a route is.
- The tests use the real context layer on a local port.

## Not for now

- Search across documents by meaning (embeddings).

## Notes for the plan

FastMCP from the `mcp` package serves the tools, stateless with JSON responses. `MultiServerMCPClient` from `langchain-mcp-adapters` calls them.
