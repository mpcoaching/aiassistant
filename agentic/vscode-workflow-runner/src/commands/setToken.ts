import * as vscode from "vscode";
import { PluginSession } from "../session";

export async function setToken(session: PluginSession): Promise<void> {
  const token = await vscode.window.showInputBox({
    prompt: "Workflow Engine API token (stored in SecretStorage)",
    password: true,
    ignoreFocusOut: true,
  });
  if (!token) {
    return;
  }
  await session.setToken(token);
  await session.refreshExplorer();
}
