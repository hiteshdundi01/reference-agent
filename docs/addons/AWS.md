# Running on AWS

From Acme Store's platform team.

<!-- An add-on brief. It builds on docs/addons/POSTGRES.md and docs/addons/SECURE.md. Copy it to docs/AWS.md to make it part of the build, then ask for a plan. -->

## Where we are

Everything runs on a laptop: the backend and the agent as FastAPI apps on two ports, with `AGENT_URL` between them. The agent's app already speaks Amazon Bedrock AgentCore Runtime's contract: `POST /invocations` and `GET /ping`.

## What we need

- **The backend on AWS Lambda** behind a function URL, with the built dashboard served beside the API.
- **The agent on AgentCore Runtime.** The app's wrapper becomes `BedrockAgentCoreApp`, and the harness, the tools and the graph are unchanged. The backend reaches the agent through `invoke_agent_runtime` when `AGENT_RUNTIME` names its runtime, and over HTTP otherwise, both in `backend/agent_service.py`.
- **Secrets in AgentCore Identity:** the agent's key, the provider's key and the database's address are fetched on the agent's first request, never kept in a file.
- **Optionally, the agent's tools through an AgentCore Gateway,** whose policy refuses any refund over the limit even if everything else fails.
- **A teardown** that removes every resource the deployment made, and a note of what it costs while it runs.

## Rules

- Each deployable imports with only its dependency group installed. `npm run check:server` and `npm run check:agent` already check this; the package is built from those groups for Linux.
- Nothing is created or deleted on AWS unless a person asks for it.
- The checks never reach AWS: they use stand-ins for the runtime, the gateway and Identity.

## Not for now

- Running in more than one region.
- Autoscaling beyond what Lambda and AgentCore Runtime give.
- Infrastructure for anything other than the backend, the agent and their secrets.
