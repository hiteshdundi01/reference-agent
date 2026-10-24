import type { State } from "./types";

// What each state is called, and its color from docs/BRAND.md.

export const STATES: Record<State, { label: string; tone: string }> = {
  waiting: { label: "Waiting", tone: "info" },
  working: { label: "Working", tone: "primary" },
  stalled: { label: "Stalled", tone: "warning" },
  held: { label: "Held for a supervisor", tone: "warning" },
  refunded: { label: "Refunded", tone: "success" },
  declined: { label: "Declined", tone: "danger" },
  escalated: { label: "Escalated", tone: "neutral" },
  failed: { label: "Failed", tone: "danger" },
};

export const STARTABLE: readonly State[] = ["waiting", "failed", "stalled"];
