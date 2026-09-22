import { test, expect } from "@playwright/test";

const API_BASE = process.env.VITE_API_TARGET || "http://localhost:8000";

async function paperclipChat(message: string, sessionId?: string) {
  const res = await fetch(`${API_BASE}/assistant/paperclip-chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, ...(sessionId ? { session_id: sessionId } : {}) }),
  });
  expect(res.ok).toBe(true);
  return res.json();
}

test.describe("Paperclip-managed Assistant chat", () => {
  test.slow();

  test("paperclip-chat returns AI-generated response with paperclip runtime", async () => {
    const data = await paperclipChat("What is 17 multiplied by 6?");

    expect(data.status).toBe("completed");
    expect(data.message).toContain("102");
    expect(data.telemetry.runtime).toBe("paperclip");
    expect(data.telemetry.agent_id).toBeTruthy();
    expect(data.telemetry.work_id).toBeTruthy();
    expect(data.telemetry.model).toBeTruthy();
    expect(data.telemetry.ai_invoked).toBe(true);
    expect(data.telemetry.ai_success).toBe(true);
    expect(data.telemetry.ai_latency_ms).toBeGreaterThan(0);
  });

  test("multi-turn conversation through paperclip preserves context", async () => {
    const firstData = await paperclipChat("My favourite number is 17.");
    const sessionId = firstData.session_id;

    const secondData = await paperclipChat("What number did I just tell you?", sessionId);
    expect(secondData.status).toBe("completed");
    expect(secondData.session_id).toBe(sessionId);
    expect(secondData.message).toContain("17");
  });

  test("different sessions are isolated", async () => {
    const firstData = await paperclipChat("My favourite number is 42.");
    const sessionA = firstData.session_id;

    const secondData = await paperclipChat("My favourite number is 99.");
    const sessionB = secondData.session_id;

    expect(sessionA).not.toBe(sessionB);

    const followupAData = await paperclipChat("What number did I just tell you?", sessionA);
    expect(followupAData.message).toContain("42");
  }, 300000);
});
