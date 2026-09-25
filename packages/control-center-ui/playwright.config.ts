import { defineConfig } from "@playwright/test";

// Critical-path e2e runs against the dev tier (nginx → dev-controller:8443).
// CI starts the dev stack and maps dev.local.test to the host before running.
//
// In CI, E2E_BASE_URL points at the already-running dev-control-center-ui
// container, so the local vite webServer below must stay off; for local runs
// the base URL defaults to dev.local.test and vite is booted on demand.
const baseURL = process.env.E2E_BASE_URL || "http://dev.local.test";
const externalTarget = Boolean(process.env.E2E_BASE_URL);

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30000,
  expect: { timeout: 10000 },
  fullyParallel: true,
  reporter: [["junit", { outputFile: "playwright-results.xml" }]],
  use: {
    baseURL,
    headless: true,
    trace: "retain-on-failure",
  },
  // For local runs, boot the vite dev server if not already running.
  webServer: externalTarget
    ? undefined
    : {
        command: "npm run dev -- --port 8443 --host 0.0.0.0",
        url: "http://localhost:8443",
        reuseExistingServer: true,
        timeout: 120000,
      },
});
