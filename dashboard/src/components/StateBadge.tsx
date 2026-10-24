import { STATES } from "../states";
import type { State } from "../types";

export function StateBadge({ state }: Readonly<{ state: State }>) {
  const { label, tone } = STATES[state];
  return <span className={`badge tone-${tone}`}>{label}</span>;
}
