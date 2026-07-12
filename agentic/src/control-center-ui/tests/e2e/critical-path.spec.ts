import { test, expect } from "@playwright/test";

// Thin critical-path e2e slice against the DEV environment (http://dev.local.test).
// This is intentionally small — broad e2e coverage is out of scope.

test("app shell loads", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Control Center")).toBeVisible();
});

test("workflows tab is reachable and shows empty state without backend", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Workflows" }).click();
  await expect(page.getByText(/No workflows found/i)).toBeVisible();
});
