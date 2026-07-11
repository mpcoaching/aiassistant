import * as vscode from "vscode";
import { PluginSession } from "../session";

export async function refresh(session: PluginSession): Promise<void> {
  await session.refreshExplorer();
}
