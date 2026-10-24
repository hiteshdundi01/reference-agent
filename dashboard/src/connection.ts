import { forget, token } from "./auth";

// How the dashboard sends each request to the backend and reads its answer or
// its refusal. Only api.ts uses it.

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

const SIGN_IN_AGAIN = 401;

function reasonFor(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return "Some of what was sent isn't valid";
  return "Something went wrong";
}

export async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  const signIn = token();
  if (signIn) headers.set("Authorization", `Bearer ${signIn}`);
  const response = await fetch(`/api${path}`, { ...init, headers });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as {
      detail?: unknown;
    };
    if (response.status === SIGN_IN_AGAIN && signIn) forget();
    throw new ApiError(response.status, reasonFor(body.detail));
  }
  return (await response.json()) as T;
}

export function post<T>(path: string, body?: object): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}
