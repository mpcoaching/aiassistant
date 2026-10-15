import * as vscode from "vscode";
import type { WorkflowSummary } from "./types";
import { PluginSession } from "./session";
import { runFile, runWorkflow } from "./commands/run";
import { stopWorkflow } from "./commands/stop";
import { setToken } from "./commands/setToken";
import { refresh } from "./commands/refresh";

let session: PluginSession | undefined;

export function activate(context: vscode.ExtensionContext): void {
  const output = vscode.window.createOutputChannel("Workflow Runner");
  output.show(true);
  session = new PluginSession(output, context.secrets);

  const explorer = vscode.window.registerTreeDataProvider(
    "workflowRunner.explorer",
    session.explorer
  );

  const runCmd = vscode.commands.registerCommand(
    "workflowRunner.run",
    (summary?: WorkflowSummary) => {
      if (!summary) {
        vscode.window.showWarningMessage("Run requires a workflow from the Explorer.");
        return;
      }
      return runWorkflow(session!, summary);
    }
  );

  // A "chain" workflow is executed server-side by the Workflow Engine; the
  // client path is identical to a normal run.
  const runChainCmd = vscode.commands.registerCommand(
    "workflowRunner.runChain",
    (summary?: WorkflowSummary) => {
      if (!summary) {
        vscode.window.showWarningMessage("Run Chain requires a workflow from the Explorer.");
        return;
      }
      return runWorkflow(session!, summary);
    }
  );

  // Right-click a workflow YAML file in the Explorer file tree.
  const runFileCmd = vscode.commands.registerCommand(
    "workflowRunner.runFile",
    (uri?: vscode.Uri) => runFile(session!, uri!)
  );

  const stopCmd = vscode.commands.registerCommand(
    "workflowRunner.stop",
    (summary?: WorkflowSummary) => stopWorkflow(session!, summary)
  );

  const refreshCmd = vscode.commands.registerCommand("workflowRunner.refresh", () =>
    refresh(session!)
  );

  const setTokenCmd = vscode.commands.registerCommand("workflowRunner.setToken", () =>
    setToken(session!)
  );

  context.subscriptions.push(
    explorer,
    runCmd,
    runChainCmd,
    runFileCmd,
    stopCmd,
    refreshCmd,
    setTokenCmd,
    output
  );

  // Initial catalog load (best-effort; surfaces an error item if no token yet).
  void session.refreshExplorer();
}

export function deactivate(): void {
  session = undefined;
}
