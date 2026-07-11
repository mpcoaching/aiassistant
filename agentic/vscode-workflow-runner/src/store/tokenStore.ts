import * as vscode from "vscode";

const TOKEN_KEY = "workflowRunner.engineToken";

/**
 * Stores the Workflow Engine API token in VS Code SecretStorage so it is never
 * persisted to settings.json or committed to the repository.
 */
export class TokenStore {
  constructor(private readonly secrets: vscode.SecretStorage) {}

  async get(): Promise<string | undefined> {
    return this.secrets.get(TOKEN_KEY);
  }

  async set(token: string): Promise<void> {
    await this.secrets.store(TOKEN_KEY, token);
  }

  async delete(): Promise<void> {
    await this.secrets.delete(TOKEN_KEY);
  }
}
