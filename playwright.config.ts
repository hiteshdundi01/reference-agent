import { defineConfig } from "@playwright/test";
import {
  AGENT_KEY,
  AGENT_STAND_IN,
  AUTH_SECRET,
  BACKEND,
  DASHBOARD,
  PASSWORD,
} from "./e2e/servers";

// The tests run their own backend on a database of its own, a stand-in for the
// agent and the dashboard, on ports of their own, whatever the shell has.
export default defineConfig({
  testDir: "e2e",
  outputDir: "e2e/test-results",
  reporter: "list",
  // The tests share one database, so they run one at a time.
  workers: 1,
  use: { baseURL: DASHBOARD },
  webServer: [
    {
      command: `uv run -m backend.seed && uv run -m uvicorn backend.main:app --port ${new URL(BACKEND).port}`,
      url: `${BACKEND}/api/health`,
      env: {
        APP_DB: "e2e/app.db",
        AGENT_URL: AGENT_STAND_IN,
        AGENT_KEY,
        AUTH_SECRET,
        USER_PASSWORD: PASSWORD,
      },
    },
    {
      command: "node e2e/agent_stand_in.mjs",
      url: `${AGENT_STAND_IN}/ping`,
      env: { PORT: new URL(AGENT_STAND_IN).port, APP_API: BACKEND, AGENT_KEY },
    },
    {
      command: `npx vite dashboard --port ${new URL(DASHBOARD).port} --strictPort`,
      url: DASHBOARD,
      env: { APP_API: BACKEND },
    },
  ],
});
