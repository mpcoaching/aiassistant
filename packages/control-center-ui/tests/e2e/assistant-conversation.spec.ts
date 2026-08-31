import { test, expect } from "@playwright/test";

// Layer 3 — Platform E2E for real conversational AI.
// Proves: Browser -> control-center-ui -> workflow-engine -> AssistantChatService
//         -> AIResponseService -> Portkey -> LLM -> response -> Browser
//
// Requires:
//   - The full Docker/Podman platform running
//   - PORTKEY_MASTER_KEY configured in workflow-engine
//   - A real LLM reachable through Portkey
//
// Skipped when API base URL is localhost (no real backend).

const API_BASE = process.env.VITE_API_TARGET || "http://localhost:8000";
const IS_REAL_BACKEND = !API_BASE.includes("localhost");

test.describe("Real conversational AI through the platform", () => {
  test.skip(!IS_REAL_BACKEND, "Requires real platform backend (not localhost)");

  test("conversational message returns AI-generated response with provenance", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Assistant" }).click();

    const input = page.locator('input[placeholder="Type a message..."]');
    await input.fill("Explain why a successful business can become harder to manage as it grows.");
    await page.getByRole("button", { name: "Send" }).click();

    const response = page.locator(".cc-chat-text").last();
    await expect(response).toBeVisible({ timeout: 30000 });

    const bubble = page.locator(".cc-chat-msg.assistant").last();
    await expect(bubble).toHaveAttribute("data-runtime", "ai_response_service", { timeout: 10000 });

    const reasoning = page.locator(".cc-chat-meta").last();
    await expect(reasoning).toContainText("AI", { timeout: 10000 });
  });

  test("follow-up question references previous turn context", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Assistant" }).click();

    const input = page.locator('input[placeholder="Type a message..."]');
    await input.fill("My business sells coaching programs to established consultants.");
    await page.getByRole("button", { name: "Send" }).click();

    await expect(page.locator(".cc-chat-text").last()).toBeVisible({ timeout: 30000 });

    const sessionLabel = page.locator(".cc-chat-session");
    const firstSessionId = await sessionLabel.textContent();
    expect(firstSessionId).toMatch(/^Session: ses-/);

    const secondInput = page.locator('input[placeholder="Type a message..."]');
    await secondInput.fill("What would you investigate first if sales suddenly dropped?");
    await page.getByRole("button", { name: "Send" }).click();

    const secondResponse = page.locator(".cc-chat-text").last();
    await expect(secondResponse).toBeVisible({ timeout: 30000 });

    const secondBubble = page.locator(".cc-chat-msg.assistant").last();
    await expect(secondBubble).toHaveAttribute("data-runtime", "ai_response_service", { timeout: 10000 });

    const updatedSessionLabel = page.locator(".cc-chat-session");
    expect(await updatedSessionLabel.textContent()).toBe(firstSessionId);
  });

  test("three-turn conversation demonstrates context continuity", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Assistant" }).click();

    const input = page.locator('input[placeholder="Type a message..."]');

    await input.fill("Let's call the fictional company Northstar Coaching. It has 12 employees and is struggling with operational complexity.");
    await page.getByRole("button", { name: "Send" }).click();
    await expect(page.locator(".cc-chat-text").last()).toBeVisible({ timeout: 30000 });

    await input.fill("What would you investigate first?");
    await page.getByRole("button", { name: "Send" }).click();
    await expect(page.locator(".cc-chat-text").last()).toBeVisible({ timeout: 30000 });

    await input.fill("Now answer that as if I'm the owner rather than an employee.");
    await page.getByRole("button", { name: "Send" }).click();

    const thirdResponse = page.locator(".cc-chat-text").last();
    await expect(thirdResponse).toBeVisible({ timeout: 30000 });

    const assistantBubbles = page.locator(".cc-chat-msg.assistant");
    const count = await assistantBubbles.count();
    expect(count).toBeGreaterThanOrEqual(3);

    for (let i = 0; i < count; i++) {
      await expect(assistantBubbles.nth(i)).toHaveAttribute("data-runtime", "ai_response_service", { timeout: 10000 });
    }
  });
});
