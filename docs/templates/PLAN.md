# Plan: <the brief's name>

<!-- Written by the coding agent from a brief, as docs/PROCESS.md describes. The person reviews it before anything is built. -->

## What this builds

<Two or three sentences: what the work adds, and what it leaves for later.>

## Design

### Modules

| Module        | What it is for | Uses |
| ------------- | -------------- | ---- |
| `backend/...` | ...            | ...  |

<Check the design against docs/CODE_STANDARDS.md: one way to reach each service, one job per module, and no borrowed helpers.>

### State machine

<For anything that moves through states, write the states as a table. The backend owns the states, and each move is a conditional update.>

| From | Operation (caller) | To  | Refused when |
| ---- | ------------------ | --- | ------------ |
| ...  | ...                | ... | ...          |

### The agent's instructions

<Their goal, what the agent has to work from and what done looks like. Never a list of steps. Anything that must always happen is code, and the plan says where.>

### Choices and why

- <Each choice that isn't obvious, with the alternative you turned down and why.>

## Phases

### Phase 1: <name>

<What it builds and why it comes first.>

- [ ] <A criterion you can check yourself: a test that passes, a command and its output, an API call and its response, or a page in the browser>
- [ ] `npm run check` passes

### Phase 2: <name>

...

<Usually 5 or 6 phases. The last includes any live run with a real model, and says what it may spend.>
