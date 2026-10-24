import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import {
  HELD,
  MORGAN,
  ORDER,
  RILEY,
  STEP,
  answering as answeringOnly,
  at,
  detail,
  refusal,
} from "../testing";

// Every request page reads its order too.
const answering = (table: Record<string, unknown>) =>
  answeringOnly({ "GET /orders/ORD-5003": ORDER, ...table });

afterEach(() => {
  vi.useRealTimers();
});

test("a request shows its details and steps", async () => {
  answering({
    "GET /requests/REQ-1003": detail(),
    "GET /requests/REQ-1003/steps": [STEP],
  });
  at("/requests/REQ-1003", RILEY);
  expect(
    await screen.findByRole("heading", { name: "REQ-1003" }),
  ).toBeDefined();
  expect(screen.getByText("The table top has a deep split.")).toBeDefined();
  expect(screen.getByText("read_order({})")).toBeDefined();
  expect(screen.getByText("No decision yet.")).toBeDefined();
});

test("starting the agent asks the backend and shows the work", async () => {
  const sent = answering({
    "GET /requests/REQ-1003": [detail(), detail({ state: "escalated" })],
    "GET /requests/REQ-1003/steps": [[], [STEP]],
    "POST /requests/REQ-1003/start": detail({ state: "working", attempt: 1 }),
  });
  at("/requests/REQ-1003", RILEY);
  await userEvent.click(
    await screen.findByRole("button", { name: "Start the agent" }),
  );
  expect(await screen.findByText("Escalated")).toBeDefined();
  expect(
    sent.some(
      (s) => s.method === "POST" && s.path === "/requests/REQ-1003/start",
    ),
  ).toBe(true);
});

test("a start the backend refuses says why", async () => {
  answering({
    "GET /requests/REQ-1003": detail(),
    "GET /requests/REQ-1003/steps": [],
    "POST /requests/REQ-1003/start": refusal(503, "The agent isn't running"),
  });
  at("/requests/REQ-1003", RILEY);
  await userEvent.click(
    await screen.findByRole("button", { name: "Start the agent" }),
  );
  expect((await screen.findByRole("alert")).textContent).toBe(
    "The agent isn't running",
  );
});

test("a working request is read again until the agent is done", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  answering({
    "GET /requests/REQ-1003": [detail({ state: "working", attempt: 1 }), HELD],
    "GET /requests/REQ-1003/steps": [[], [STEP]],
  });
  at("/requests/REQ-1003", MORGAN);
  expect(await screen.findByText("Working")).toBeDefined();
  await vi.advanceTimersByTimeAsync(1100);
  expect(await screen.findByText("Held for a supervisor")).toBeDefined();
  expect(screen.queryByRole("button", { name: "Start the agent" })).toBeNull();
});

test("a supervisor signs off a held refund", async () => {
  const sent = answering({
    "GET /requests/REQ-1003": [HELD, detail({ state: "refunded" })],
    "GET /requests/REQ-1003/steps": [],
    "POST /requests/REQ-1003/sign-off": detail({ state: "refunded" }),
  });
  at("/requests/REQ-1003", MORGAN);
  expect(
    await screen.findByText("Damaged on arrival, with a photo."),
  ).toBeDefined();
  await userEvent.click(
    screen.getByRole("button", { name: "Sign off and refund $320.00" }),
  );
  expect(await screen.findByText("Refunded")).toBeDefined();
  expect(sent.find((s) => s.path.endsWith("/sign-off"))?.body).toEqual({
    decision_id: 7,
  });
});

test("a supervisor sends a decision back with a note", async () => {
  const sent = answering({
    "GET /requests/REQ-1003": [HELD, detail({ state: "working", revision: 2 })],
    "GET /requests/REQ-1003/steps": [],
    "POST /requests/REQ-1003/send-back": detail({
      state: "working",
      revision: 2,
    }),
  });
  at("/requests/REQ-1003", MORGAN);
  const sendBack = await screen.findByRole("button", { name: "Send back" });
  expect((sendBack as HTMLButtonElement).disabled).toBe(true);
  await userEvent.type(
    screen.getByLabelText("Note for the agent"),
    "Check the photo date.",
  );
  await userEvent.click(sendBack);
  await waitFor(() => {
    expect(sent.find((s) => s.path.endsWith("/send-back"))?.body).toEqual({
      decision_id: 7,
      note: "Check the photo date.",
    });
  });
});

test("a supervisor's refused sign-off says why", async () => {
  answering({
    "GET /requests/REQ-1003": HELD,
    "GET /requests/REQ-1003/steps": [],
    "POST /requests/REQ-1003/sign-off": refusal(
      409,
      "Decision 7 isn't the one waiting",
    ),
  });
  at("/requests/REQ-1003", MORGAN);
  await userEvent.click(
    await screen.findByRole("button", { name: /Sign off/ }),
  );
  expect((await screen.findByRole("alert")).textContent).toBe(
    "Decision 7 isn't the one waiting",
  );
});

test("a rep sees a held refund but can't sign it off", async () => {
  answering({
    "GET /requests/REQ-1003": HELD,
    "GET /requests/REQ-1003/steps": [],
  });
  at("/requests/REQ-1003", RILEY);
  expect(await screen.findByText("Held for a supervisor")).toBeDefined();
  expect(screen.queryByRole("button", { name: /Sign off/ })).toBeNull();
});

test("a refund, a send-back and a failure all show", async () => {
  answering({
    "GET /requests/REQ-1003": detail({
      state: "failed",
      failure: "RuntimeError: the model was down",
      refund: {
        amount: 45,
        issued_at: "2026-10-24T10:00:00Z",
        signed_off_by: "morgan.diaz@acme.example",
      },
      send_back: {
        note: "Look again.",
        sent_by: "morgan.diaz@acme.example",
        sent_at: "2026-10-24T10:00:00Z",
        revision: 2,
      },
    }),
    "GET /requests/REQ-1003/steps": [],
  });
  at("/requests/REQ-1003", RILEY);
  expect(
    await screen.findByText("RuntimeError: the model was down"),
  ).toBeDefined();
  expect(screen.getByText(/signed off by morgan.diaz/)).toBeDefined();
  expect(screen.getByText(/Look again\./)).toBeDefined();
  expect(screen.getByRole("button", { name: "Start the agent" })).toBeDefined();
});

test("a request that can't load says why", async () => {
  answering({
    "GET /requests/REQ-9999": refusal(404, "There is no request REQ-9999"),
  });
  at("/requests/REQ-9999", RILEY);
  expect((await screen.findByRole("alert")).textContent).toBe(
    "There is no request REQ-9999",
  );
});

test("a request shows the order it is about", async () => {
  answering({
    "GET /requests/REQ-1003": detail(),
    "GET /requests/REQ-1003/steps": [],
    "GET /orders/ORD-5003": {
      ...ORDER,
      delivered_at: null,
      carrier_status: "lost",
    },
  });
  at("/requests/REQ-1003", RILEY);
  expect(
    await screen.findByRole("heading", { name: "Order ORD-5003" }),
  ).toBeDefined();
  expect(screen.getByText("Oak dining table")).toBeDefined();
  expect(screen.getByText("$20.00")).toBeDefined();
  expect(screen.getByText(/Expected 2026-10-08/)).toBeDefined();
  expect(screen.getByText(/carrier: lost/)).toBeDefined();
});
