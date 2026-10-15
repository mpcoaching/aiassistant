import * as vscode from "vscode";
import * as path from "path";
import type { RunResponse, WorkflowSummary, WorkflowRunStatus } from "../types";
import { isTerminal } from "../types";
import { isSecretKey } from "../util/redact";
import { errorMessage, PluginSession } from "../session";

function delay(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    if (signal) {
      if (signal.aborted) {
        return resolve();
      }
      signal.addEventListener("abort", () => resolve(), { once: true });
    }
    setTimeout(resolve, ms);
  });
}

/** Convert a file URI to a repo-relative path used as the workflow ref. */
export function repoRelative(uri: vscode.Uri): string {
  const folders = vscode.workspace.workspaceFolders;
  if (folders && folders.length > 0) {
    const rel = path.relative(folders[0].uri.fsPath, uri.fsPath).replace(/\\/g, "/");
    return rel;
  }
  return uri.fsPath;
}

/**
 * Run a workflow directly from a right-clicked file in the Explorer. The
 * workflow_ref is the repo-relative path; required inputs are taken from the
 * catalog when the file is known to the engine, otherwise prompted minimally.
 */
export async function runFile(
  session: PluginSession,
  uri: vscode.Uri
): Promise<void> {
  if (!uri) {
    vscode.window.showWarningMessage("Run requires a workflow file.");
    return;
  }
  const ref = repoRelative(uri);
  const base = path.basename(uri.fsPath, path.extname(uri.fsPath));

  // Smart check: only run if the engine says this file is actually a workflow.
  let v;
  try {
    v = await session.ensureClient().then((c) => c.validate(ref));
  } catch (e) {
    vscode.window.showErrorMessage(`Workflow Runner: ${errorMessage(e)}`);
    return;
  }
  if (!v.is_workflow) {
    vscode.window.showWarningMessage(
      `Not a workflow file: ${v.reason ?? "unrecognized structure"}`
    );
    return;
  }

  const summary: WorkflowSummary = {
    ref,
    name: v.name ?? base,
    role: v.role,
    inputs: v.inputs ?? [],
  };
  return runWorkflow(session, summary);
}

/**
 * Run a workflow: collect missing inputs, submit to the Workflow Engine, then
 * observe progress via SSE (with polling fallback). Cancellable via the
 * notification's Cancel button, which calls stop on the engine.
 */
export async function runWorkflow(
  session: PluginSession,
  summary: WorkflowSummary
): Promise<void> {
  let client;
  try {
    client = await session.ensureClient();
  } catch (e) {
    vscode.window.showErrorMessage(`Workflow Runner: ${errorMessage(e)}`);
    return;
  }

  const inputs: Record<string, string> = {};
  for (const name of summary.inputs ?? []) {
    const value = await vscode.window.showInputBox({
      prompt: `Input '${name}' for ${summary.name}`,
      password: isSecretKey(name),
      ignoreFocusOut: true,
    });
    if (value === undefined) {
      session.log("Run cancelled by user.");
      return;
    }
    inputs[name] = value;
  }

  let resp: RunResponse;
  try {
    session.log(`Submitting workflow ${summary.name} (${summary.ref})`);
    resp = await client.run({ workflow_ref: summary.ref, inputs, role: session.userRoles[0] });
  } catch (e) {
    vscode.window.showErrorMessage(`Workflow Runner: ${errorMessage(e)}`);
    return;
  }

  const runId = resp.run_id;
  session.activeRuns.set(summary.ref, runId);
  session.log(`Run ${runId} accepted (status ${resp.status}).`);
  vscode.window.showInformationMessage(`Workflow '${summary.name}' started (${runId}).`);

  await observeRun(session, runId);
}

async function observeRun(session: PluginSession, runId: string): Promise<void> {
  const client = session.client!;
  const abort = new AbortController();

  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: `Workflow ${runId}`,
      cancellable: true,
    },
    async (progress, token) => {
      token.onCancellationRequested(() => {
        session.log(`Cancellation requested for ${runId}; sending stop.`);
        client.stop(runId).catch((e) => session.log(`stop failed: ${errorMessage(e)}`));
        abort.abort();
      });

      let final: WorkflowRunStatus | undefined;

      try {
        await client.subscribeEvents(
          runId,
          (ev) => {
            session.log(`event: ${ev.type}`);
            if (ev.type === "WorkflowProgress") {
              progress.report({
                message: `${ev.step.step_name} (${ev.current_step}/${ev.total_steps})`,
              });
            } else if (ev.type === "WorkflowCompleted") {
              vscode.window.showInformationMessage(`Workflow completed: ${runId}`);
            } else if (ev.type === "WorkflowFailed") {
              vscode.window.showErrorMessage(`Workflow failed: ${ev.error}`);
            } else if (ev.type === "WorkflowCancelled") {
              vscode.window.showWarningMessage(`Workflow cancelled: ${runId}`);
            }
          },
          abort.signal
        );
      } catch {
        session.log("SSE unavailable; falling back to polling.");
        while (!abort.signal.aborted) {
          const st = await client
            .getStatus(runId, abort.signal)
            .catch(() => undefined);
          if (!st) {
            break;
          }
          final = st;
          progress.report({
            message: `${st.current_step}/${st.total_steps} — ${st.status}`,
          });
          if (isTerminal(st.status)) {
            break;
          }
          await delay(1000, abort.signal);
        }
      }

      if (!final) {
        final = await client.getStatus(runId).catch(() => undefined);
      }
      if (final) {
        session.log(
          `Final status: ${final.status}` + (final.error ? ` error=${final.error}` : "")
        );
      }
      session.activeRuns.delete(runId);
    }
  );
}
