import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The backend the dev server sends /api to.
const BACKEND = process.env.APP_API ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  // The dashboard needs nothing from .env, and the tests must never read it.
  envDir: false,
  server: { proxy: { "/api": BACKEND } },
  test: {
    environment: "jsdom",
    setupFiles: ["src/setupTests.ts"],
    coverage: {
      include: ["src/**"],
      exclude: ["src/main.tsx", "src/**/*.test.{ts,tsx}", "src/setupTests.ts"],
      thresholds: { lines: 80, functions: 80, branches: 80, statements: 80 },
    },
  },
});
