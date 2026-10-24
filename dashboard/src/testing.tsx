import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { vi } from "vitest";
import { Pages } from "./App";
import { forget, remember } from "./auth";
import type { Order, RequestDetail, RequestSummary, Step, User } from "./types";

// What the tests share: people to sign in as, records to answer with, a stand-in
// for fetch, and rendering a page at a path.

export const RILEY: User = {
  email: "riley.chen@acme.example",
  name: "Riley Chen",
  role: "rep",
};
export const MORGAN: User = {
  email: "morgan.diaz@acme.example",
  name: "Morgan Diaz",
  role: "supervisor",
};

export const SUMMARY: RequestSummary = {
  id: "REQ-1003",
  customer_name: "Casey Nguyen",
  order_id: "ORD-5003",
  amount: 320,
  submitted_at: "2026-10-09T18:05:00Z",
  state: "waiting",
};

export function detail(changes: Partial<RequestDetail> = {}): RequestDetail {
  return {
    ...SUMMARY,
    customer_id: "CUS-203",
    evidence: "photo",
    reason: "The table top has a deep split.",
    attempt: 0,
    revision: 0,
    failure: null,
    decision: null,
    refund: null,
    send_back: null,
    ...changes,
  };
}

export const HELD = detail({
  state: "held",
  attempt: 1,
  revision: 1,
  decision: {
    id: 7,
    decision: "approve",
    amount: 320,
    section: "Section 3",
    reason: "Damaged on arrival, with a photo.",
    decided_by: "agent (anthropic:claude-opus-5-5)",
    decided_at: "2026-10-24T10:00:00Z",
  },
});

export const STEP: Step = {
  id: 1,
  attempt: 1,
  at: "2026-10-24T10:00:00Z",
  kind: "tool_call",
  text: "read_order({})",
};

export interface Sent {
  method: string;
  path: string;
  body: unknown;
}

// An answer is a body, a Response, or a function of the request that gives one.
function answerTo(given: unknown, init: RequestInit): Response {
  const value: unknown =
    typeof given === "function"
      ? (given as (i: RequestInit) => unknown)(init)
      : given;
  return value instanceof Response ? value : Response.json(value);
}

// Answers fetch from a table of "METHOD /path" to an answer, or a list of
// answers given in turn, the last one again once they run out; keeps every
// request sent.
export function answering(table: Record<string, unknown>): Sent[] {
  const sent: Sent[] = [];
  const turns: Record<string, number> = {};
  vi.stubGlobal("fetch", (url: string, init: RequestInit = {}) => {
    const method = init.method ?? "GET";
    const path = url.replace(/^\/api/, "");
    const route = `${method} ${path}`;
    const body: unknown =
      typeof init.body === "string" ? JSON.parse(init.body) : undefined;
    sent.push({ method, path, body });
    if (!(route in table)) {
      return Promise.resolve(
        Response.json({ detail: `no ${route}` }, { status: 404 }),
      );
    }
    const given: unknown = table[route];
    const turn = turns[route] ?? 0;
    turns[route] = turn + 1;
    const answers: unknown[] =
      Array.isArray(given) && isTurns(route, given) ? given : [given];
    return Promise.resolve(
      answerTo(answers[Math.min(turn, answers.length - 1)], init),
    );
  });
  return sent;
}

// A list is answers in turn, except for a list route whose answer is itself a
// list of records (such as GET /requests), given as [[...], [...]] to take turns.
function isTurns(route: string, given: unknown[]): boolean {
  const listRoute = route === "GET /requests" || route.endsWith("/steps");
  if (!listRoute) return true;
  return given.length > 0 && given.every((answer) => Array.isArray(answer));
}

export const refusal = (status: number, detail: unknown) =>
  Response.json({ detail }, { status });

export function at(path: string, who?: User) {
  forget();
  if (who) remember({ token: `token-of-${who.email}`, user: who });
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Pages />
    </MemoryRouter>,
  );
}

export const ORDER: Order = {
  id: "ORD-5003",
  customer_id: "CUS-203",
  placed_at: "2026-10-02",
  expected_delivery: "2026-10-08",
  delivered_at: "2026-10-08",
  carrier_status: "delivered",
  items: [
    {
      sku: "TBL-OAK-6",
      name: "Oak dining table",
      price: 300,
      quantity: 1,
      final_sale: false,
    },
  ],
  shipping: 20,
  total: 320,
};
