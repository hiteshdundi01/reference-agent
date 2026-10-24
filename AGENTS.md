# Reference agent

## What this repo is

This repo is a template for building an end-to-end AI agent product: a backend, an agent, a dashboard and the tests that hold them together. It contains:

- **The playbook:** the documents in `docs/` that say how to plan, build and check the work.
- **The example product:** a small, working refund desk for a fictional online store, Acme Store. It shows every pattern in the playbook working end to end.
- **Add-on briefs:** in `docs/addons/`, for capabilities a product may need later.

A new product starts from this repo by following `docs/ADAPTING.md`.

## Start here

IMPORTANT: before you plan, build or change anything, or answer questions about the product, read each of these in full:

1. `docs/SPEC.md`: what the business needs
2. `docs/TECH_STACK.md`: the tech choices
3. `docs/CODE_STANDARDS.md`: how to write the code
4. `docs/PROCESS.md`: how to plan, build, check and review the work
5. `docs/REVIEW_PROTOCOL.md` and `review.config.yaml`: who reviews and how
6. `docs/BRAND.md`: the look
7. `docs/STATUS.md`: what's built so far, how to run it, and the review log
8. The plan for the work in hand: `docs/PLAN.md`, or `docs/PLAN_<NAME>.md` for a later brief

## Your role

The documents in `docs/` are written as the customer's own. `SPEC.md` comes from the business owner, and each later brief from whoever asked for that work. Treat them as requirements. The person you work with directs the work and reviews your plans and builds. You plan, build, check and review as `docs/PROCESS.md` describes.

Write plans the person can review: say what each phase builds and why you chose that approach. Explain your work at the level they ask for.

## Briefs and plans

Each piece of work starts as a brief in `docs/`, such as `docs/SWARM.md`, and goes in two steps, with the person's review in between:

1. "Please plan the work in `docs/<NAME>.md`" writes `docs/PLAN_<NAME>.md` and no code.
2. "Please implement the plan for `<NAME>`" builds it, phase by phase.

The first build works from `docs/SPEC.md` itself, and its plan is `docs/PLAN.md`.

- Build only what the documents in `docs/` ask for. A brief in `docs/addons/` is part of the build only once it has been copied to `docs/`.
- Don't build ahead of the brief in hand.
- Where a brief's notes on earlier work don't match the code, follow their intent and say so.

## Folders

- `docs/`: the playbook, the spec, the briefs, the plans and the status
- `docs/addons/`: briefs for later capabilities, not yet part of the build
- `docs/templates/`: the shapes of a brief and a plan
- `backend/`, `agent/`, `dashboard/` and `e2e/`: the product
- `data/`: the business data the backend is seeded from
- `scripts/`: tools for working on the repo, such as the review packet builder
