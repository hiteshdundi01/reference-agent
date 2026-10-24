// A stand-in for the agent's app in the end-to-end tests. It answers
// /invocations and /ping as the agent does, and plays a scripted decision for
// each request through the backend's API with the agent's key.
import { createServer } from "node:http";

const BACKEND = `${process.env.APP_API}/api`;
const KEY = process.env.AGENT_KEY;

// What the stand-in decides on each request it is asked to work.
const SCRIPTS = {
  "REQ-1001": { decision: "approve", amount: 45, section: "Section 3" },
  "REQ-1003": { decision: "approve", amount: 320, section: "Section 3" },
  "REQ-1011": { decision: "approve", amount: 640, section: "Section 3" },
};
const REASON = "The goods arrived damaged, which Section 3 refunds in full.";

async function backend(method, path, body) {
  const response = await fetch(`${BACKEND}${path}`, {
    method,
    headers: { "X-API-Key": KEY, "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return response.json();
}

async function work(requestId) {
  const request = await backend("GET", `/requests/${requestId}`);
  const step = (kind, text) =>
    backend("POST", `/requests/${requestId}/steps`, {
      attempt: request.attempt,
      kind,
      text,
    });
  await step("tool_call", "read_order({})");
  await step("tool_result", "The order was delivered.");
  await backend("POST", `/requests/${requestId}/decision`, {
    attempt: request.attempt,
    revision: request.revision,
    reason: REASON,
    decided_by: "agent (stand-in)",
    ...SCRIPTS[requestId],
  });
}

function reply(response, status, body) {
  response.writeHead(status, { "Content-Type": "application/json" });
  response.end(JSON.stringify(body));
}

createServer((request, response) => {
  if (request.method === "GET" && request.url === "/ping") {
    reply(response, 200, { status: "Healthy" });
    return;
  }
  let text = "";
  request.on("data", (chunk) => (text += chunk));
  request.on("end", () => {
    const payload = JSON.parse(text);
    if (payload.operation === "health")
      return reply(response, 200, { healthy: true });
    if (request.headers.authorization !== `Bearer ${KEY}`) {
      return reply(response, 401, {
        detail: "The agent's key is missing or wrong",
      });
    }
    reply(response, 200, { accepted: true });
    if (payload.operation === "work") void work(payload.request_id);
  });
}).listen(Number(process.env.PORT), "127.0.0.1");
