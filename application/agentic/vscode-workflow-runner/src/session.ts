import * as vscode from "vscode";
import { getConfig } from "./config";
import { TokenStore } from "./store/tokenStore";
import { EngineError, WorkflowEngineClient } from "./api/client";
import { WorkflowExplorer } from "./explorer/workflowExplorer";
import { redactLine } from "./util/redact";
import type { WorkflowSummary } from "./types";

/** Shared plugin state, created once in `activate`. */
export class PluginSession {
  readonly output: vscode.OutputChannel;
  readonly tokenStore: TokenStore;
  readonly explorer: WorkflowExplorer;
  client: WorkflowEngineClient | undefined;
  userRoles: string[] = [];
  /** ref -> active run id, for the Stop command. */
  readonly activeRuns = new Map<string, string>();

  constructor(output: vscode.OutputChannel, secrets: vscode.SecretStorage) {
    this.output = output;
    this.tokenStore = new TokenStore(secrets);
    this.explorer = new WorkflowExplorer();
  }

  log(line: string): void {
    this.output.appendLine(redactLine(line));
  }

  /** Decode roles from the JWT payload (UI gating only; server is authoritative). */
  private decodeRoles(token: string): string[] {
    try {
      const part = token.split(".")[1];
      if (!part) {
        return [];
      }
      const json = JSON.parse(Buffer.from(part, "base64url").toString("utf8"));
      const raw = json.roles ?? json.role ?? json.groups ?? json.scope;
      if (Array.isArray(raw)) {
        return raw.map(String);
      }
      if (typeof raw === "string") {
        return raw.split(/[\s,]+/).filter(Boolean);
      }
    } catch {
      // ignore — server re-validates
    }
    return [];
  }

  async ensureClient(): Promise<WorkflowEngineClient> {
    if (this.client) {
      return this.client;
    }
    const token = await this.tokenStore.get();
    if (!token) {
      throw new EngineError(
        "No Workflow Engine token configured. Run 'Workflow Runner: Set Token'.",
        401
      );
    }
    this.userRoles = this.decodeRoles(token);
    this.explorer.setUserRoles(this.userRoles);
    const cfg = getConfig();
    this.client = new WorkflowEngineClient(cfg.engineUrl, token, (l) => this.log(l));
    return this.client;
  }

  async setToken(token: string): Promise<void> {
    await this.tokenStore.set(token);
    this.client = undefined; // recreate with the new token on next use
    this.userRoles = this.decodeRoles(token);
    this.explorer.setUserRoles(this.userRoles);
    this.log("Workflow Engine token stored in SecretStorage.");
  }

  async refreshExplorer(): Promise<void> {
    try {
      const client = await this.ensureClient();
      const workflows: WorkflowSummary[] = await client.listWorkflows();
      this.explorer.setWorkflows(workflows, this.userRoles);
      this.log(`Loaded ${workflows.length} workflows from catalog.`);
    } catch (e) {
      const msg = errorMessage(e);
      this.explorer.setError(msg);
      this.log(`Catalog refresh failed: ${msg}`);
      vscode.window.showErrorMessage(`Workflow Runner: ${msg}`);
    }
  }
}

export function errorMessage(e: unknown): string {
  if (e instanceof Error) {
    return e.message;
  }
  return String(e);
}
