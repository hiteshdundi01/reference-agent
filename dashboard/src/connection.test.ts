import { expect, test } from "vitest";
import { getRequest, sendBack } from "./api";
import { remember, signedIn } from "./auth";
import { ApiError } from "./connection";
import { RILEY, answering, refusal } from "./testing";

test("a request carries the signed-in person's token", async () => {
  remember({ token: "the-token", user: RILEY });
  let seen = "";
  answering({
    "GET /requests/REQ-1": (init: RequestInit) => {
      seen = new Headers(init.headers).get("Authorization") ?? "";
      return { id: "REQ-1" };
    },
  });
  await getRequest("REQ-1");
  expect(seen).toBe("Bearer the-token");
});

test("an expired sign-in is forgotten", async () => {
  remember({ token: "old", user: RILEY });
  answering({ "GET /requests/REQ-1": refusal(401, "Sign in again") });
  await expect(getRequest("REQ-1")).rejects.toBeInstanceOf(ApiError);
  expect(signedIn()).toBeNull();
});

test("a refusal with a list of problems reads plainly", async () => {
  answering({
    "POST /requests/REQ-1/send-back": refusal(422, [{ msg: "too long" }]),
  });
  await expect(sendBack("REQ-1", 7, "x")).rejects.toThrow(
    "Some of what was sent isn't valid",
  );
});

test("a refusal with no reason still reads plainly", async () => {
  answering({ "GET /requests/REQ-1": new Response("oops", { status: 500 }) });
  await expect(getRequest("REQ-1")).rejects.toThrow("Something went wrong");
});
