import { expect, test } from "vitest";
import { money } from "./format";

test("money reads in US dollars", () => {
  expect(money(1250)).toBe("$1,250.00");
  expect(money(45.5)).toBe("$45.50");
});
