import * as vscode from "vscode";
import type { WorkflowSummary } from "../types";
import { errorMessage, PluginSession } from "../session";

export async function stopWorkflow(
  session: PluginSession,
  summary?: WorkflowSummary
): Promise<void> {
  const client = session.client;
  if (!client) {
    vscode.window.showWarningMessage("No active Workflow Engine connection.");
    return;
  }

  let runId: string | undefined;
  let label: string | undefined;

  if (summary && session.activeRuns.has(summary.ref)) {
    runId = session.activeRuns.get(summary.ref);
    label = summary.name;
  } else if (session.activeRuns.size > 0) {
    const picks = Array.from(session.activeRuns.entries()).map(([ref, id]) => ({
      label: ref,
      runId: id,
    }));
    const pick = await vscode.window.showQuickPick(picks, {
      placeHolder: "Select a running workflow to stop",
    });
    if (!pick) {
      return;
    }
    runId = pick.runId;
    label = pick.label;
  } else {
    vscode.window.showInformationMessage("No running workflows to stop.");
    return;
  }

  try {
    await client.stop(runId!);
    session.log(`Stop requested for ${label} (${runId}).`);
    vscode.window.showInformationMessage(`Stop requested for ${label}.`);
  } catch (e) {
    vscode.window.showErrorMessage(`Workflow Runner: ${errorMessage(e)}`);
  }
}
