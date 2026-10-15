import type {
  RunRequest,
  RunResponse,
  WorkflowEvent,
  WorkflowRunStatus,
  WorkflowSummary,
  WorkflowValidation,
} from "../types";

export type LogFn = (line: string) => void;

/**
 * Typed thin client for the Workflow Engine service. The plugin never executes
 * skills or tools; it submits requests and observes progress. All transport is
 * HTTP(S) with a bearer token; SSE is consumed via fetch streaming so it works
 * in the VS Code extension host (Node).
 */
export class WorkflowEngineClient {
  private readonly baseUrl: string;
  private readonly token: string;
  private readonly log?: LogFn;

  constructor(baseUrl: string, token: string, log?: LogFn) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.token = token;
    this.log = log;
  }

  private headers(extra?: Record<string, string>): Record<string, string> {
    return {
      Authorization: `Bearer ${this.token}`,
      Accept: "application/json",
      ...extra,
    };
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown
  ): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method,
      headers: this.headers(
        body ? { "Content-Type": "application/json" } : undefined
      ),
      body: body ? JSON.stringify(body) : undefined,
    });

    if (res.status === 401) {
      throw new EngineError("Unauthorized: check the Workflow Engine token.", 401);
    }
    if (res.status === 403) {
      throw new EngineError("Forbidden: your role may not run this workflow.", 403);
    }
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new EngineError(`Workflow Engine error ${res.status}: ${text}`, res.status);
    }

    const ct = res.headers.get("content-type") || "";
    if (ct.includes("application/json")) {
      return (await res.json()) as T;
    }
    return undefined as unknown as T;
  }

  /** GET /workflows — catalog of runnable workflows. */
  listWorkflows(signal?: AbortSignal): Promise<WorkflowSummary[]> {
    return this.request<WorkflowSummary[]>("GET", "/workflows", undefined);
  }

  /** POST /workflows/run — submit a workflow run. */
  run(req: RunRequest, signal?: AbortSignal): Promise<RunResponse> {
    return this.request<RunResponse>("POST", "/workflows/run", req);
  }
  /** POST /workflows/validate — ask the engine if a ref is a real workflow. */
  async validate(workflowRef: string, signal?: AbortSignal): Promise<WorkflowValidation> {
    try {
      return await this.request<WorkflowValidation>("POST", "/workflows/validate", {
        workflow_ref: workflowRef,
      });
    } catch {
      // Endpoint may be absent on some engines; degrade to "attempt run" so we
      // don't block valid workflows. The engine will reject invalid ones.
      return { is_workflow: true, name: workflowRef };
    }
  }

  /** GET /workflows/{run_id} — current status. */
  getStatus(runId: string, signal?: AbortSignal): Promise<WorkflowRunStatus> {
    return this.request<WorkflowRunStatus>("GET", `/workflows/${encodeURIComponent(runId)}`);
  }

  /** POST /workflows/{run_id} — stop a running workflow. */
  async stop(runId: string, signal?: AbortSignal): Promise<void> {
    await this.request<void>("POST", `/workflows/${encodeURIComponent(runId)}/stop`);
  }

  /**
   * Subscribe to WorkflowProgress SSE for a run. Resolves when the stream ends
   * (completion/cancellation) or when the AbortSignal fires.
   */
  async subscribeEvents(
    runId: string,
    onEvent: (e: WorkflowEvent) => void,
    signal?: AbortSignal
  ): Promise<void> {
    const res = await fetch(
      `${this.baseUrl}/workflows/${encodeURIComponent(runId)}/events`,
      { headers: this.headers(), signal }
    );
    if (!res.ok || !res.body) {
      throw new EngineError(`Event stream failed (${res.status})`, res.status);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }
        buffer += decoder.decode(value, { stream: true });

        let sep: number;
        while ((sep = buffer.indexOf("\n\n")) >= 0) {
          const frame = buffer.slice(0, sep);
          buffer = buffer.slice(sep + 2);
          const dataLines = frame
            .split("\n")
            .filter((l) => l.startsWith("data:"))
            .map((l) => l.replace(/^data:\s?/, ""))
            .join("\n");
          if (dataLines) {
            try {
              onEvent(JSON.parse(dataLines) as WorkflowEvent);
            } catch (e) {
              this.log?.(`[warn] dropped malformed event: ${String(e)}`);
            }
          }
        }
      }
    } finally {
      reader.cancel().catch(() => undefined);
    }
  }
}

export class EngineError extends Error {
  constructor(message: string, public readonly status?: number) {
    super(message);
    this.name = "EngineError";
  }
}
