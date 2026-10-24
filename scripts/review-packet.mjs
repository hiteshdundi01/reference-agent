// Builds the inline prompt for an MVP-tier review and checks it with gitleaks
// (docs/REVIEW_PROTOCOL.md). It never runs a reviewer.
//
//   node scripts/review-packet.mjs --unit "Phase 3" --plan docs/PLAN.md \
//     --section "Phase 3" [--section ...] [--base main] [--checks review/checks.txt] \
//     [--notes review/notes.md] > review/prompt.md
//
// With no --base it reviews what is staged, against HEAD. With --base it reviews
// HEAD against its merge base with that ref, as a whole-branch review does.
import { parseArgs } from "node:util";
import { PacketError, buildPacket, gitleaks } from "./review/packet.mjs";

const { values } = parseArgs({
  options: {
    unit: { type: "string" },
    plan: { type: "string" },
    section: { type: "string", multiple: true },
    base: { type: "string" },
    checks: { type: "string" },
    notes: { type: "string" },
    author: { type: "string" },
  },
});

try {
  const { prompt, summary } = buildPacket(values, {
    cwd: process.cwd(),
    scan: gitleaks,
  });
  process.stdout.write(prompt);
  process.stderr.write(`review-packet: ${summary}\n`);
} catch (error) {
  if (!(error instanceof PacketError)) throw error;
  process.stderr.write(`review-packet: ${error.message}\n`);
  process.exitCode = 1;
}
