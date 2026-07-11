import * as vscode from "vscode";

export const CONFIG_SECTION = "workflowRunner";

export interface PluginConfig {
  /** Base URL of the Workflow Engine service. */
  engineUrl: string;
  /** Optional Agent Bus endpoint for event subscription. */
  agentBusUrl?: string;
  /** Optional OTEL/observability endpoint. */
  otelUrl?: string;
  /** Polling interval (ms) when SSE is unavailable. */
  pollIntervalMs: number;
  /** Only enable Run for workflows with a verified trust signature. */
  trustedOnly: boolean;
}

export function getConfig(): PluginConfig {
  const c = vscode.workspace.getConfiguration(CONFIG_SECTION);
  return {
    engineUrl: (c.get<string>("engineUrl") || "http://localhost:8000").replace(/\/$/, ""),
    agentBusUrl: c.get<string>("agentBusUrl") || undefined,
    otelUrl: c.get<string>("otelUrl") || undefined,
    pollIntervalMs: c.get<number>("pollIntervalMs") || 1000,
    trustedOnly: c.get<boolean>("trustedOnly") || false,
  };
}
