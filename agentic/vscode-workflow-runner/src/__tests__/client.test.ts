import { test } from "node:test";
import assert from "node:assert/strict";
import * as http from "node:http";
import type { AddressInfo } from "node:net";
import { EngineError, WorkflowEngineClient } from "../api/client";
import type { WorkflowEvent, WorkflowSummary } from "../types";

function startMock(
  handler: (req: http.IncomingMessage, res: http.ServerResponse) => void
): Promise<{ url: string; close: () => void }> {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => handler(req, res));
    server.listen(0, "127.0.0.1", () => {
      const addr = server.address() as AddressInfo;
      resolve({
        url: `http://127.0.0.1:${addr.port}`,
        close: () => server.close(),
      });
    });
  });
}

const CATALOG: WorkflowSummary[] = [
  { ref: "wf/a.yaml", name: "A", role: ["developer"], inputs: ["x"], outputs: ["y"] },
];

test("listWorkflows fetches the catalog", async () => {
  const mock = await startMock((_req, res) => {
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify(CATALOG));
  });
  try {
    const client = new WorkflowEngineClient(mock.url, "tok");
    const wf = await client.listWorkflows();
    assert.equal(wf.length, 1);
    assert.equal(wf[0].name, "A");
  } finally {
    mock.close();
  }
});

test("run returns a run_id", async () => {
  const mock = await startMock((req, res) => {
    if (req.method === "POST") {
      res.statusCode = 202;
      res.setHeader("Content-Type", "application/json");
      res.end(JSON.stringify({ run_id: "run-1", status: "running" }));
    }
  });
  try {
    const client = new WorkflowEngineClient(mock.url, "tok");
    const r = await client.run({ workflow_ref: "wf/a.yaml", inputs: { x: "1" } });
    assert.equal(r.run_id, "run-1");
  } finally {
    mock.close();
  }
});

test("getStatus returns current status", async () => {
  const status = {
    run_id: "run-1",
    workflow_ref: "wf/a.yaml",
    status: "completed",
    current_step: 2,
    total_steps: 2,
  };
  const mock = await startMock((req, res) => {
    if (req.url === "/workflows/run-1") {
      res.setHeader("Content-Type", "application/json");
      res.end(JSON.stringify(status));
    }
  });
  try {
    const client = new WorkflowEngineClient(mock.url, "tok");
    const s = await client.getStatus("run-1");
    assert.equal(s.status, "completed");
  } finally {
    mock.close();
  }
});

test("stop posts to the stop endpoint", async () => {
  let stopped = false;
  const mock = await startMock((req, res) => {
    if (req.method === "POST" && req.url === "/workflows/run-1/stop") {
      stopped = true;
      res.statusCode = 202;
      res.end();
    }
  });
  try {
    const client = new WorkflowEngineClient(mock.url, "tok");
    await client.stop("run-1");
    assert.equal(stopped, true);
  } finally {
    mock.close();
  }
});

test("401 surfaces an EngineError", async () => {
  const mock = await startMock((_req, res) => {
    res.statusCode = 401;
    res.end("no token");
  });
  try {
    const client = new WorkflowEngineClient(mock.url, "tok");
    await assert.rejects(() => client.listWorkflows(), EngineError);
  } finally {
    mock.close();
  }
});

test("subscribeEvents parses SSE frames", async () => {
  const mock = await startMock((req, res) => {
    if (req.url === "/workflows/run-1/events") {
      res.setHeader("Content-Type", "text/event-stream");
      res.writeHead(200);
      res.write("data: " + JSON.stringify({ type: "WorkflowStarted", run_id: "run-1", workflow_ref: "wf/a.yaml" }) + "\n\n");
      res.write("data: " + JSON.stringify({ type: "WorkflowCompleted", run_id: "run-1" }) + "\n\n");
      res.end();
    }
  });
  try {
    const client = new WorkflowEngineClient(mock.url, "tok");
    const events: WorkflowEvent[] = [];
    await client.subscribeEvents("run-1", (e) => events.push(e));
    assert.equal(events.length, 2);
    assert.equal(events[0].type, "WorkflowStarted");
    assert.equal(events[1].type, "WorkflowCompleted");
  } finally {
    mock.close();
  }
});
