import { screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { RILEY, SUMMARY, answering, at, refusal } from "../testing";

test("the queue lists each request with its state", async () => {
  answering({
    "GET /requests": [
      SUMMARY,
      { ...SUMMARY, id: "REQ-1001", state: "refunded", amount: 45 },
    ],
  });
  at("/", RILEY);
  expect(await screen.findByRole("link", { name: "REQ-1001" })).toBeDefined();
  expect(screen.getByText("$320.00")).toBeDefined();
  expect(screen.getByText("Waiting").className).toContain("tone-info");
  expect(screen.getByText("Refunded").className).toContain("tone-success");
});

test("the queue says when it can't load", async () => {
  answering({ "GET /requests": refusal(500, "The database is down") });
  at("/", RILEY);
  expect((await screen.findByRole("alert")).textContent).toBe(
    "The database is down",
  );
});

test("an expired sign-in goes back to signing in", async () => {
  answering({ "GET /requests": refusal(401, "Sign in first") });
  at("/", RILEY);
  expect(await screen.findByLabelText("Email")).toBeDefined();
  expect(screen.queryByText(/Riley Chen/)).toBeNull();
});
