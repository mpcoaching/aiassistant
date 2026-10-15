import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60000,
  expect: { timeout: 15000 },
  fullyParallel: false,
  reporter: [["junit", { outputFile: "playwright-results.xml" }]],
  use: {
    baseURL: "http://localhost:5173",
    headless: true,
    trace: "retain-on-failure",
  },
  webServer: {
    command: "VITE_API_TARGET=http://localhost:8000 npm run dev -- --port 5173 --host 0.0.0.0",
    url: "http://localhost:5173",
    reuseExistingServer: true,
    timeout: 120000,
  },
});
