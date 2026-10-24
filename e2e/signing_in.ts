import { expect, type Page } from "@playwright/test";
import { PASSWORD } from "./servers";

// Signs a person in through the sign-in page, as they would.
export async function signIn(
  page: Page,
  person: { email: string; name: string },
) {
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(person.email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(
    page.getByRole("heading", { name: "Refund requests" }),
  ).toBeVisible();
  await expect(page.getByText(person.name)).toBeVisible();
}
