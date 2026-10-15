import { test, expect } from "@playwright/test";

// Layer 3 — Platform E2E critical path.
// Runs against the full Docker Compose stack (infrastructure → platform → dev).
// Requires the `test-e2e` CI step or a locally booted equivalent.
// Thin critical-path slice — broad e2e coverage is out of scope.

test("app shell loads", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Control Center")).toBeVisible();
});

test("workflows tab is reachable and shows workflows", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Workflows" }).click();
  await expect(page.getByText(/\d+ workflow\(s\)/i)).toBeVisible();
});

test("assistant chat submits a message and shows a work result", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Assistant" }).click();

  const input = page.locator('input[placeholder="Type a message..."]');
  await input.fill("Summarise this: The company is launching a new coaching program for mid-career professionals. The program spans 12 weeks and includes weekly group coaching sessions.");

  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText("Done.")).toBeVisible({ timeout: 30000 });

  await expect(page.getByText(/Work:/)).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/Status:/)).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/Backend:/)).toBeVisible({ timeout: 5000 });
});

test("assistant chat creates a proposal for a coaching program", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Assistant" }).click();

  const input = page.locator('input[placeholder="Type a message..."]');
  await input.fill("Create a proposal for a coaching program");

  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText("Done.")).toBeVisible({ timeout: 30000 });

  await expect(page.getByText(/Work:/)).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/Status:/)).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/Backend:/)).toBeVisible({ timeout: 5000 });
});

test("assistant chat uploads a document and summarises it", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Assistant" }).click();

  const fileInput = page.locator('input[type="file"]');
  const tempFile = Buffer.from(
    "The new coaching program is designed to help mid-career professionals transition into leadership roles. The program spans 12 weeks and includes weekly group coaching sessions."
  );
  await fileInput.setInputFiles({ name: "quarterly-report.txt", mimeType: "text/plain", buffer: tempFile });

  const messageInput = page.locator('input[placeholder="Type a message..."]');
  await messageInput.fill("Summarise this");

  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText("Done.")).toBeVisible({ timeout: 30000 });

  await expect(page.getByText(/Summary:/)).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/Work:/)).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/Status:/)).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/Backend:/)).toBeVisible({ timeout: 5000 });
});

test("assistant chat plans a birthday party with assumptions", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Assistant" }).click();

  const input = page.locator('input[placeholder="Type a message..."]');
  await input.fill("Plan a birthday party for 20 people");

  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText("Done.")).toBeVisible({ timeout: 30000 });

  await expect(page.getByText(/Action Plan/)).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/Assumptions/)).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/Work:/)).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/Status:/)).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/Backend:/)).toBeVisible({ timeout: 5000 });
});

test("assistant chat clarifies an underspecified plan", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Assistant" }).click();

  const input = page.locator('input[placeholder="Type a message..."]');
  await input.fill("Plan the party");

  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.locator(".cc-chat-human-question")).toHaveText("What kind of event are you planning?", { timeout: 10000 });

  const responseInput = page.locator('input[placeholder="Type your response..."]');
  await responseInput.fill("A birthday party for 20 people");

  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText("Done.")).toBeVisible({ timeout: 30000 });

  await expect(page.getByText(/Action Plan/)).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/Work:/)).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/Status:/)).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/Backend:/)).toBeVisible({ timeout: 5000 });
});

test("assistant chat plans from document context", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Assistant" }).click();

  const fileInput = page.locator('input[type="file"]');
  const tempFile = Buffer.from(
    "3-day hiking trip in the Swiss Alps for two people. " +
    "Accommodation in Grindelwald. Approximately 15 km hiking per day. " +
    "Planned for June."
  );
  await fileInput.setInputFiles({ name: "hiking-trip.txt", mimeType: "text/plain", buffer: tempFile });

  const input = page.locator('input[placeholder="Type a message..."]');
  await input.fill("Plan this");

  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText("Done.")).toBeVisible({ timeout: 30000 });

  await expect(page.getByText(/Action Plan/)).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/Assumptions/)).toBeVisible({ timeout: 5000 });
  await expect(page.locator(".cc-chat-text").last()).toContainText("hiking", { timeout: 5000 });
  await expect(page.getByText(/Work:/)).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/Status:/)).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/Backend:/)).toBeVisible({ timeout: 5000 });
});

test("assistant chat clarifies when document lacks subject", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Assistant" }).click();

  const fileInput = page.locator('input[type="file"]');
  const tempFile = Buffer.from(
    "Venue available for 50 people. Budget is $1000. " +
    "Scheduled for next month."
  );
  await fileInput.setInputFiles({ name: "event-details.txt", mimeType: "text/plain", buffer: tempFile });

  const input = page.locator('input[placeholder="Type a message..."]');
  await input.fill("Plan this");

  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.locator(".cc-chat-human-question")).toHaveText("What kind of event or activity are you planning?", { timeout: 10000 });

  const responseInput = page.locator('input[placeholder="Type your response..."]');
  await responseInput.fill("A birthday party for 50 people");

  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText("Done.")).toBeVisible({ timeout: 30000 });

  await expect(page.getByText(/Action Plan/)).toBeVisible({ timeout: 5000 });
  await expect(page.locator(".cc-chat-text").last()).toContainText("birthday", { timeout: 5000 });
  await expect(page.getByText(/Work:/)).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/Status:/)).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/Backend:/)).toBeVisible({ timeout: 5000 });
});

test("assistant chat infers hiking trip from indirect document", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Assistant" }).click();

  const fileInput = page.locator('input[type="file"]');
  const tempFile = Buffer.from(
    "We're planning to arrive in Interlaken on Tuesday and spend three days walking " +
    "through the Bernese Oberland. There are two of us. We've booked two nights in " +
    "Grindelwald. We'd like to keep the longest walking day around 15km. We have " +
    "hiking boots and packs but still need to sort weather protection and food."
  );
  await fileInput.setInputFiles({ name: "alpine-trip-notes.txt", mimeType: "text/plain", buffer: tempFile });

  const input = page.locator('input[placeholder="Type a message..."]');
  await input.fill("Plan this");

  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText("Done.")).toBeVisible({ timeout: 30000 });

  await expect(page.getByText(/Action Plan/)).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/Assumptions/)).toBeVisible({ timeout: 5000 });
  await expect(page.locator(".cc-chat-text").last()).toContainText("hiking", { timeout: 5000 });
  await expect(page.locator(".cc-chat-text").last()).toContainText("15", { timeout: 5000 });
  await expect(page.getByText(/Work:/)).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/Status:/)).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/Backend:/)).toBeVisible({ timeout: 5000 });
});

test("assistant chat analyses a business document and shows focus areas", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Assistant" }).click();

  const fileInput = page.locator('input[type="file"]');
  const tempFile = Buffer.from(
    "Q3 revenue declined 12% year-on-year, driven by lower enterprise renewals. " +
    "Customer retention fell from 84% to 76%. Support volume increased 31%, " +
    "with average response time rising from 2 hours to 8 hours. " +
    "NPS dropped from 45 to 28. Two new competitors entered the market last quarter. " +
    "Headcount is frozen until Q4."
  );
  await fileInput.setInputFiles({ name: "quarterly-business-review.txt", mimeType: "text/plain", buffer: tempFile });

  const input = page.locator('input[placeholder="Type a message..."]');
  await input.fill("Analyse this and tell me what I should focus on");

  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.locator(".cc-chat-validation")).toBeVisible({ timeout: 10000 });
  await expect(page.locator(".cc-chat-validation-header")).toHaveText("Here's what I understand", { timeout: 5000 });
  await expect(page.locator(".cc-chat-validation-proposed")).toContainText("I understand you want to", { timeout: 5000 });

  await page.locator(".cc-chat-validation-confirm").click();

  await expect(page.getByText("Done.")).toBeVisible({ timeout: 30000 });

  await expect(page.locator(".cc-chat-text").last()).toContainText("Analysis", { timeout: 5000 });
  await expect(page.locator(".cc-chat-text").last()).toContainText("Understanding", { timeout: 5000 });
  await expect(page.locator(".cc-chat-text").last()).toContainText("Prioritised Focus", { timeout: 5000 });
  await expect(page.locator(".cc-chat-text").last()).toContainText("Why this matters", { timeout: 5000 });
  await expect(page.locator(".cc-chat-text").last()).toContainText("Confidence", { timeout: 5000 });
  await expect(page.locator(".cc-chat-text").last()).toContainText("What would validate this", { timeout: 5000 });
  await expect(page.locator(".cc-chat-text").last()).toContainText("12%", { timeout: 5000 });
  await expect(page.locator(".cc-chat-text").last()).toContainText("retention", { timeout: 5000 });
  await expect(page.getByText(/Work:/)).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/Status:/)).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/Backend:/)).toBeVisible({ timeout: 5000 });
});

test("assistant chat clarifies analysis goal then executes with accumulated context", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Assistant" }).click();

  const fileInput = page.locator('input[type="file"]');
  const tempFile = Buffer.from(
    "Q3 revenue declined 12% year-on-year, driven by lower enterprise renewals. " +
    "Customer retention fell from 84% to 76%. Support volume increased 31%, " +
    "with average response time rising from 2 hours to 8 hours. " +
    "NPS dropped from 45 to 28. Two new competitors entered the market last quarter. " +
    "Headcount is frozen until Q4."
  );
  await fileInput.setInputFiles({ name: "quarterly-business-review.txt", mimeType: "text/plain", buffer: tempFile });

  const input = page.locator('input[placeholder="Type a message..."]');
  await input.fill("Analyse this");

  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.locator(".cc-chat-human-question")).toHaveText("What would you like the analysis to help you determine?", { timeout: 10000 });

  const responseInput = page.locator('input[placeholder="Type your response..."]');
  await responseInput.fill("What should I focus on to improve growth?");

  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.locator(".cc-chat-validation")).toBeVisible({ timeout: 10000 });
  await page.locator(".cc-chat-validation-confirm").click();

  await expect(page.getByText("Done.")).toBeVisible({ timeout: 30000 });

  await expect(page.locator(".cc-chat-text").last()).toContainText("Analysis", { timeout: 5000 });
  await expect(page.locator(".cc-chat-text").last()).toContainText("Understanding", { timeout: 5000 });
  await expect(page.locator(".cc-chat-text").last()).toContainText("Prioritised Focus", { timeout: 5000 });
  await expect(page.locator(".cc-chat-text").last()).toContainText("12%", { timeout: 5000 });
  await expect(page.locator(".cc-chat-text").last()).toContainText("retention", { timeout: 5000 });
  await expect(page.getByText(/Work:/)).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/Status:/)).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/Backend:/)).toBeVisible({ timeout: 5000 });
});

test("assistant chat validation confirms analysis and executes (Scenario A)", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Assistant" }).click();

  const fileInput = page.locator('input[type="file"]');
  const tempFile = Buffer.from(
    "Q3 revenue declined 12% year-on-year, driven by lower enterprise renewals. " +
    "Customer retention fell from 84% to 76%. Support volume increased 31%, " +
    "with average response time rising from 2 hours to 8 hours. " +
    "NPS dropped from 45 to 28. Two new competitors entered the market last quarter. " +
    "Headcount is frozen until Q4."
  );
  await fileInput.setInputFiles({ name: "quarterly-business-review.txt", mimeType: "text/plain", buffer: tempFile });

  const msgInput = page.locator('input[placeholder="Type a message..."]');
  await msgInput.fill("Analyse this and tell me what I should focus on");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.locator(".cc-chat-validation")).toBeVisible({ timeout: 10000 });
  await expect(page.locator(".cc-chat-validation-proposed")).toContainText("I understand you want to", { timeout: 5000 });

  await page.locator(".cc-chat-validation-confirm").click();

  await expect(page.getByText("Done.")).toBeVisible({ timeout: 30000 });
  await expect(page.getByText(/Prioritised Focus/)).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/Work:/)).toBeVisible({ timeout: 5000 });
});

test("assistant chat validation contradicts and revises goal (Scenario B)", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Assistant" }).click();

  const fileInput = page.locator('input[type="file"]');
  const tempFile = Buffer.from(
    "Q3 revenue declined 12% year-on-year, driven by lower enterprise renewals. " +
    "Customer retention fell from 84% to 76%. Support volume increased 31%, " +
    "with average response time rising from 2 hours to 8 hours. " +
    "NPS dropped from 45 to 28. Two new competitors entered the market last quarter. " +
    "Headcount is frozen until Q4."
  );
  await fileInput.setInputFiles({ name: "quarterly-business-review.txt", mimeType: "text/plain", buffer: tempFile });

  const msgInput = page.locator('input[placeholder="Type a message..."]');
  await msgInput.fill("Analyse this and tell me what I should focus on");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.locator(".cc-chat-validation")).toBeVisible({ timeout: 10000 });

  const valInput = page.locator('input[placeholder="Type your response or use the actions above..."]');
  await valInput.fill("Actually, no — analyse this to improve growth");
  await page.getByRole("button", { name: "Respond" }).click();

  await expect(page.locator(".cc-chat-validation")).toBeVisible({ timeout: 10000 });
  await expect(page.locator(".cc-chat-validation-proposed")).toContainText("improve growth", { timeout: 5000 });

  await page.locator(".cc-chat-validation-confirm").click();

  await expect(page.getByText("Done.")).toBeVisible({ timeout: 30000 });
  await expect(page.getByText(/Prioritised Focus/)).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/Work:/)).toBeVisible({ timeout: 5000 });
});

test("assistant chat validation updates understanding with additional context (Scenario C)", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Assistant" }).click();

  const fileInput = page.locator('input[type="file"]');
  const tempFile = Buffer.from(
    "Q3 revenue declined 12% year-on-year, driven by lower enterprise renewals. " +
    "Customer retention fell from 84% to 76%. Support volume increased 31%, " +
    "with average response time rising from 2 hours to 8 hours. " +
    "NPS dropped from 45 to 28. Two new competitors entered the market last quarter. " +
    "Headcount is frozen until Q4."
  );
  await fileInput.setInputFiles({ name: "quarterly-business-review.txt", mimeType: "text/plain", buffer: tempFile });

  const msgInput = page.locator('input[placeholder="Type a message..."]');
  await msgInput.fill("Analyse this and tell me what I should focus on");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.locator(".cc-chat-validation")).toBeVisible({ timeout: 10000 });

  const valInput = page.locator('input[placeholder="Type your response or use the actions above..."]');
  await valInput.fill("Also, we're currently trying to reduce churn");
  await page.getByRole("button", { name: "Respond" }).click();

  await expect(page.locator(".cc-chat-validation")).toBeVisible({ timeout: 10000 });
  await expect(page.locator(".cc-chat-validation-proposed")).toContainText("Updated understanding", { timeout: 5000 });

  await page.locator(".cc-chat-validation-confirm").click();

  await expect(page.getByText("Done.")).toBeVisible({ timeout: 30000 });
  await expect(page.getByText(/Prioritised Focus/)).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/Work:/)).toBeVisible({ timeout: 5000 });
});

test("assistant chat clarification then validation then execution (Scenario D)", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Assistant" }).click();

  const fileInput = page.locator('input[type="file"]');
  const tempFile = Buffer.from(
    "Q3 revenue declined 12% year-on-year, driven by lower enterprise renewals. " +
    "Customer retention fell from 84% to 76%. Support volume increased 31%, " +
    "with average response time rising from 2 hours to 8 hours. " +
    "NPS dropped from 45 to 28. Two new competitors entered the market last quarter. " +
    "Headcount is frozen until Q4."
  );
  await fileInput.setInputFiles({ name: "quarterly-business-review.txt", mimeType: "text/plain", buffer: tempFile });

  const msgInput = page.locator('input[placeholder="Type a message..."]');
  await msgInput.fill("Analyse this");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.locator(".cc-chat-human-question")).toHaveText("What would you like the analysis to help you determine?", { timeout: 10000 });

  const responseInput = page.locator('input[placeholder="Type your response..."]');
  await responseInput.fill("What should I focus on?");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.locator(".cc-chat-validation")).toBeVisible({ timeout: 10000 });
  await page.locator(".cc-chat-validation-confirm").click();

  await expect(page.getByText("Done.")).toBeVisible({ timeout: 30000 });
  await expect(page.locator(".cc-chat-text").last()).toContainText("Analysis", { timeout: 5000 });
  await expect(page.locator(".cc-chat-text").last()).toContainText("Prioritised Focus", { timeout: 5000 });
  await expect(page.getByText(/Work:/)).toBeVisible({ timeout: 5000 });
});
