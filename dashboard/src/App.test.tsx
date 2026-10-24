import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { signedIn } from "./auth";
import { RILEY, SUMMARY, answering, at, refusal } from "./testing";

test("every page needs a sign-in", async () => {
  answering({});
  at("/");
  expect(
    await screen.findByRole("heading", { name: "Acme refund desk" }),
  ).toBeDefined();
  expect(screen.getByLabelText("Email")).toBeDefined();
});

test("signing in remembers the person and opens the queue", async () => {
  const sent = answering({
    "POST /sign-in": { token: "t", user: RILEY },
    "GET /requests": [SUMMARY],
  });
  at("/sign-in");
  await userEvent.type(screen.getByLabelText("Email"), RILEY.email);
  await userEvent.type(screen.getByLabelText("Password"), "secret");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("link", { name: "REQ-1003" })).toBeDefined();
  expect(sent[0]?.body).toEqual({ email: RILEY.email, password: "secret" });
  expect(signedIn()?.user.name).toBe("Riley Chen");
  expect(screen.getByText(/Riley Chen/)).toBeDefined();
});

test("a wrong sign-in says why", async () => {
  answering({
    "POST /sign-in": refusal(401, "That email and password don't match"),
  });
  at("/sign-in");
  await userEvent.type(screen.getByLabelText("Email"), RILEY.email);
  await userEvent.type(screen.getByLabelText("Password"), "wrong");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect((await screen.findByRole("alert")).textContent).toBe(
    "That email and password don't match",
  );
});

test("signing out forgets the person", async () => {
  answering({ "GET /requests": [SUMMARY] });
  at("/", RILEY);
  await userEvent.click(
    await screen.findByRole("button", { name: "Sign out" }),
  );
  expect(signedIn()).toBeNull();
  expect(await screen.findByLabelText("Email")).toBeDefined();
});

test("an unknown path goes to the queue", async () => {
  answering({ "GET /requests": [SUMMARY] });
  at("/nowhere", RILEY);
  expect(
    await screen.findByRole("heading", { name: "Refund requests" }),
  ).toBeDefined();
});
