// Where the end-to-end tests run their own servers, on ports of their own so
// they never touch what `npm run dev` started, and their stand-in credentials.

export const BACKEND = "http://127.0.0.1:8100";
export const AGENT_STAND_IN = "http://127.0.0.1:8180";
export const DASHBOARD = "http://127.0.0.1:5199";

export const AGENT_KEY = "e2e-agent-key-0123456789abcdef";
export const AUTH_SECRET = "e2e-auth-secret-0123456789abcdef0123456789";
export const PASSWORD = "e2e-password";

export const PEOPLE = {
  riley: { email: "riley.chen@acme.example", name: "Riley Chen" },
  morgan: { email: "morgan.diaz@acme.example", name: "Morgan Diaz" },
};
