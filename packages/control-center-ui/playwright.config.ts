import { defineConfig } from "@playwright/test";

// Critical-path e2e runs against the dev tier (nginx → dev-controller:8443).
// CI starts the dev stack and maps dev.local.test to the host before running.
export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30000,
  expect: { timeout: 10000 },
  fullyParallel: true,
  reporter: [["junit", { outputFile: "playwright-results.xml" }]],
  use: {
    baseURL: "http://dev.local.test",
    headless: true,
    trace: "retain-on-failure",
  },
  // For local runs, boot the vite dev server if not already running.
  webServer: {
    command: "npm run dev -- --port 8443 --host 0.0.0.0",
    url: "http://localhost:8443",
    reuseExistingServer: true,
    timeout: 120000,
  },
});
