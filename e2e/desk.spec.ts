import { expect, test } from "@playwright/test";
import { PEOPLE } from "./servers";
import { signIn } from "./signing_in";

test("every page needs a sign-in", async ({ page }) => {
  await page.goto("/requests/REQ-1001");
  await expect(page.getByLabel("Email")).toBeVisible();
});

test("a wrong password is refused", async ({ page }) => {
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(PEOPLE.riley.email);
  await page.getByLabel("Password").fill("wrong");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("alert")).toHaveText(
    "That email and password don't match",
  );
});

test("a rep starts the agent and sees its steps and its decision", async ({
  page,
}) => {
  await signIn(page, PEOPLE.riley);
  await page.getByRole("link", { name: "REQ-1001" }).click();
  await page.getByRole("button", { name: "Start the agent" }).click();
  await expect(page.getByText("Refunded", { exact: true })).toBeVisible();
  await expect(page.getByText("read_order({})")).toBeVisible();
  await expect(page.getByText("Section 3", { exact: true })).toBeVisible();
  await expect(page.getByText(/Refunded \$45\.00/)).toBeVisible();
});

test("a supervisor signs off a held refund", async ({ page }) => {
  await signIn(page, PEOPLE.morgan);
  await page.getByRole("link", { name: "REQ-1003" }).click();
  await page.getByRole("button", { name: "Start the agent" }).click();
  await expect(
    page.getByText("Held for a supervisor", { exact: true }),
  ).toBeVisible();
  // The supervisor sees the order before signing off.
  await expect(
    page.getByRole("heading", { name: "Order ORD-5003" }),
  ).toBeVisible();
  await expect(page.getByText("Oak dining table")).toBeVisible();
  await page
    .getByRole("button", { name: "Sign off and refund $320.00" })
    .click();
  await expect(
    page.getByText(/signed off by morgan\.diaz@acme\.example/),
  ).toBeVisible();
  await expect(page.getByText("Refunded", { exact: true })).toBeVisible();
});

test("a rep can't sign off a held refund", async ({ page }) => {
  await signIn(page, PEOPLE.riley);
  await page.getByRole("link", { name: "REQ-1011" }).click();
  await page.getByRole("button", { name: "Start the agent" }).click();
  await expect(
    page.getByText("Held for a supervisor", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: /Sign off/ })).toHaveCount(0);
});
