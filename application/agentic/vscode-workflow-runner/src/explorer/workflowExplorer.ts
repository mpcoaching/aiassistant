import * as vscode from "vscode";
import type { WorkflowSummary } from "../types";
import { isRoleAuthorized } from "../util/authorize";

export class ErrorItem extends vscode.TreeItem {
  constructor(message: string) {
    super(`⚠ ${message}`, vscode.TreeItemCollapsibleState.None);
    this.contextValue = "workflow-error";
    this.iconPath = new vscode.ThemeIcon("error");
  }
}

export class WorkflowItem extends vscode.TreeItem {
  constructor(
    public readonly summary: WorkflowSummary,
    public readonly userRoles: string[]
  ) {
    super(summary.name, vscode.TreeItemCollapsibleState.None);
    this.description = summary.description ?? summary.ref;
    this.tooltip = summary.ref;
    const authorized = isRoleAuthorized(userRoles, summary.role);
    this.contextValue = authorized ? "workflow" : "workflow-unauthorized";
    this.iconPath = new vscode.ThemeIcon(authorized ? "rocket" : "lock");
    if (authorized) {
      this.command = {
        command: "workflowRunner.run",
        title: "Run Workflow",
        arguments: [summary],
      };
    }
  }
}

export class WorkflowExplorer implements vscode.TreeDataProvider<WorkflowItem | ErrorItem> {
  private workflows: WorkflowSummary[] = [];
  private error: string | undefined;
  private userRoles: string[] = [];
  private readonly _onDidChangeTreeData = new vscode.EventEmitter<
    WorkflowItem | ErrorItem | undefined | void
  >();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  /** Public read access for file-based run lookup. */
  getWorkflows(): WorkflowSummary[] {
    return this.workflows;
  }

  setWorkflows(workflows: WorkflowSummary[], userRoles: string[] = []): void {
    this.workflows = workflows;
    this.userRoles = userRoles;
    this.error = undefined;
    this._onDidChangeTreeData.fire();
  }

  setUserRoles(userRoles: string[]): void {
    this.userRoles = userRoles;
    this._onDidChangeTreeData.fire();
  }

  setError(error: string): void {
    this.error = error;
    this._onDidChangeTreeData.fire();
  }

  refresh(): void {
    this._onDidChangeTreeData.fire();
  }

  getTreeItem(element: WorkflowItem | ErrorItem): vscode.TreeItem {
    return element;
  }

  getChildren(element?: WorkflowItem | ErrorItem): (WorkflowItem | ErrorItem)[] {
    if (element) {
      return [];
    }
    if (this.error) {
      return [new ErrorItem(this.error)];
    }
    if (this.workflows.length === 0) {
      return [new ErrorItem("No workflows. Run 'Workflow Runner: Refresh'.")];
    }
    return this.workflows.map((w) => new WorkflowItem(w, this.userRoles));
  }
}
