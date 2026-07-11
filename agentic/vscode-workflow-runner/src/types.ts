/**
 * Shared types for the Workflow Engine thin-client plugin.
 * These mirror the schemas in `contract/workflow-engine.yaml`.
 */

export type RunStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "paused"
  | "cancelled";

export interface WorkflowSummary {
  ref: string;
  name: string;
  description?: string;
  role?: string[];
  inputs?: string[];
  outputs?: string[];
}

export interface StepResultDTO {
  step_name: string;
  step_type: string;
  status: RunStatus;
  error?: string | null;
  duration_seconds?: number | null;
}

export interface WorkflowRunStatus {
  run_id: string;
  workflow_ref: string;
  workflow_name?: string;
  status: RunStatus;
  current_step: number;
  total_steps: number;
  step_results?: StepResultDTO[];
  outputs?: Record<string, unknown> | null;
  error?: string | null;
}

export interface RunRequest {
  workflow_ref: string;
  inputs?: Record<string, string>;
  role?: string;
  callback?: string;
}

export interface RunResponse {
  run_id: string;
  status: RunStatus;
}

export type WorkflowEvent =
  | { type: "WorkflowStarted"; run_id: string; workflow_ref: string }
  | {
      type: "WorkflowProgress";
      run_id: string;
      current_step: number;
      total_steps: number;
      step: StepResultDTO;
    }
  | { type: "WorkflowCompleted"; run_id: string; outputs?: Record<string, unknown> }
  | { type: "WorkflowFailed"; run_id: string; error: string }
  | { type: "WorkflowCancelled"; run_id: string };

export const TERMINAL_STATUSES: ReadonlySet<RunStatus> = new Set<RunStatus>([
  "completed",
  "failed",
  "cancelled",
]);

export function isTerminal(status: RunStatus): boolean {
  return TERMINAL_STATUSES.has(status);
}

export interface WorkflowValidation {
  is_workflow: boolean;
  name?: string;
  role?: string[];
  inputs?: string[];
  outputs?: string[];
  reason?: string;
}
