import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import Chat from "../../src/components/Chat.jsx";

vi.mock("../../src/api.js", () => ({
  chat: vi.fn(),
  chatResume: vi.fn(),
  executeCapability: vi.fn(),
  createCapabilityRequest: vi.fn(),
  esc: (s) => String(s ?? ""),
}));

import * as api from "../../src/api.js";

beforeEach(() => {
  vi.clearAllMocks();
  api.chat.mockResolvedValue({
    message: "OK",
    status: "pending",
    session_id: "ses-1",
  });
  api.executeCapability.mockResolvedValue({
    outputs: { artifact_id: "art-1" },
    artifacts: [],
    telemetry: {},
  });
  api.createCapabilityRequest.mockResolvedValue({
    request_id: "req-1",
    action: "approved",
    status: "draft",
    concept_id: "cap-1",
    message: "Capability request approved.",
  });
});

function typeAndSend(text) {
  const input = screen.getByPlaceholderText("Type a message...");
  fireEvent.change(input, { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
}

describe("Chat capability-first routing (Increment 5)", () => {
  it("renders normal chat without capability UI when no candidates", async () => {
    render(<Chat toast={() => {}} />);
    typeAndSend("hello");
    await waitFor(() => expect(screen.queryByText("Available capabilities")).not.toBeInTheDocument());
  });

  it("renders capability candidate cards when response contains candidates", async () => {
    api.chat.mockResolvedValue({
      message: "Select a capability",
      status: "awaiting_capability_selection",
      session_id: "ses-1",
      capability_candidates: [
        { id: "cap-1", name: "create_test_artifact", description: "Creates a test artifact", kind: "tool", execution_mode: "compiled", tags: ["test"] },
        { id: "cap-2", name: "deploy_service", description: "Deploys a service", kind: "skill", execution_mode: "ai_mediated", tags: ["deploy"] },
      ],
    });
    render(<Chat toast={() => {}} />);
    typeAndSend("create a test artifact");
    await waitFor(() => expect(screen.getByText("create_test_artifact")).toBeInTheDocument());
    expect(screen.getByText("deploy_service")).toBeInTheDocument();
    expect(screen.getByText("Creates a test artifact")).toBeInTheDocument();
    expect(screen.getByText("Deploys a service")).toBeInTheDocument();
  });

  it("renders multiple candidates independently", async () => {
    api.chat.mockResolvedValue({
      message: "Select a capability",
      status: "awaiting_capability_selection",
      session_id: "ses-1",
      capability_candidates: [
        { id: "cap-1", name: "cap-a", description: "A", kind: "tool", execution_mode: "compiled", tags: [] },
        { id: "cap-2", name: "cap-b", description: "B", kind: "skill", execution_mode: "ai_mediated", tags: [] },
      ],
    });
    render(<Chat toast={() => {}} />);
    typeAndSend("do something");
    await waitFor(() => expect(screen.getByText("cap-a")).toBeInTheDocument());
    expect(screen.getByText("cap-b")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Use this capability" }).length).toBe(2);
  });

  it("selecting a capability invokes executeCapability", async () => {
    api.chat.mockResolvedValue({
      message: "Select a capability",
      status: "awaiting_capability_selection",
      session_id: "ses-1",
      capability_candidates: [
        { id: "cap-1", name: "create_test_artifact", description: "Creates a test artifact", kind: "tool", execution_mode: "compiled", tags: [] },
      ],
    });
    render(<Chat toast={() => {}} />);
    typeAndSend("create a test artifact");
    await waitFor(() => expect(screen.getByText("create_test_artifact")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Use this capability" }));
    await waitFor(() => expect(api.executeCapability).toHaveBeenCalledWith("cap-1", {}));
  });

  it("capability is not executed merely by receiving chat()", async () => {
    api.chat.mockResolvedValue({
      message: "Select a capability",
      status: "awaiting_capability_selection",
      session_id: "ses-1",
      capability_candidates: [
        { id: "cap-1", name: "create_test_artifact", description: "Creates a test artifact", kind: "tool", execution_mode: "compiled", tags: [] },
      ],
    });
    render(<Chat toast={() => {}} />);
    typeAndSend("create a test artifact");
    await waitFor(() => expect(screen.getByText("create_test_artifact")).toBeInTheDocument());
    expect(api.executeCapability).not.toHaveBeenCalled();
  });

  it("'None of these matches' opens the request form", async () => {
    api.chat.mockResolvedValue({
      message: "Select a capability",
      status: "awaiting_capability_selection",
      session_id: "ses-1",
      capability_candidates: [
        { id: "cap-1", name: "create_test_artifact", description: "Creates a test artifact", kind: "tool", execution_mode: "compiled", tags: [] },
      ],
    });
    render(<Chat toast={() => {}} />);
    typeAndSend("create a test artifact");
    await waitFor(() => expect(screen.getByText("create_test_artifact")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "None of these matches" }));
    await waitFor(() => expect(screen.getByPlaceholderText("Name")).toBeInTheDocument());
    expect(screen.getByPlaceholderText("Purpose")).toBeInTheDocument();
  });

  it("request form validates required fields", async () => {
    api.chat.mockResolvedValue({
      message: "Select a capability",
      status: "awaiting_capability_selection",
      session_id: "ses-1",
      capability_candidates: [
        { id: "cap-1", name: "cap-1", description: "d", kind: "tool", execution_mode: "compiled", tags: [] },
      ],
    });
    render(<Chat toast={() => {}} />);
    typeAndSend("do something");
    await waitFor(() => expect(screen.getByText("cap-1")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "None of these matches" }));
    await waitFor(() => expect(screen.getByPlaceholderText("Name")).toBeInTheDocument());

    const submitBtn = screen.getByRole("button", { name: "Submit request" });
    expect(submitBtn).toBeDisabled();
    fireEvent.change(screen.getByPlaceholderText("Name"), { target: { value: "new-cap" } });
    expect(submitBtn).toBeDisabled();
    fireEvent.change(screen.getByPlaceholderText("Purpose"), { target: { value: "does things" } });
    expect(submitBtn).not.toBeDisabled();
  });

  it("submitting the form calls createCapabilityRequest", async () => {
    api.chat.mockResolvedValue({
      message: "Select a capability",
      status: "awaiting_capability_selection",
      session_id: "ses-1",
      capability_candidates: [
        { id: "cap-1", name: "cap-1", description: "d", kind: "tool", execution_mode: "compiled", tags: [] },
      ],
    });
    render(<Chat toast={() => {}} />);
    typeAndSend("do something");
    await waitFor(() => expect(screen.getByText("cap-1")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "None of these matches" }));
    await waitFor(() => expect(screen.getByPlaceholderText("Name")).toBeInTheDocument());

    fireEvent.change(screen.getByPlaceholderText("Name"), { target: { value: "new-cap" } });
    fireEvent.change(screen.getByPlaceholderText("Purpose"), { target: { value: "does things" } });
    fireEvent.change(screen.getByPlaceholderText("Inputs (comma-separated)"), { target: { value: "a,b" } });
    fireEvent.change(screen.getByPlaceholderText("Outputs (comma-separated)"), { target: { value: "c,d" } });
    fireEvent.change(screen.getByPlaceholderText("Acceptance criteria (comma-separated)"), { target: { value: "fast, reliable" } });

    fireEvent.click(screen.getByRole("button", { name: "Submit request" }));
    await waitFor(() => expect(api.createCapabilityRequest).toHaveBeenCalledTimes(1));
    const callArgs = api.createCapabilityRequest.mock.calls[0];
    expect(callArgs[0]).toMatch(/^req-\d+$/);
    expect(callArgs[1].capability_request.name).toBe("new-cap");
    expect(callArgs[1].capability_request.purpose).toBe("does things");
    expect(callArgs[1].capability_request.inputs).toEqual([{ name: "a", type: "string" }, { name: "b", type: "string" }]);
    expect(callArgs[1].capability_request.outputs).toEqual([{ name: "c", type: "string" }, { name: "d", type: "string" }]);
    expect(callArgs[1].capability_request.acceptance_criteria).toEqual(["fast", "reliable"]);
  });

  it("existing normal chat behavior remains unchanged", async () => {
    api.chat.mockResolvedValue({
      message: "I'll help with that.",
      status: "pending",
      session_id: "ses-1",
    });
    render(<Chat toast={() => {}} />);
    typeAndSend("do something");
    await waitFor(() => expect(screen.getByText("I'll help with that.")).toBeInTheDocument());
    expect(screen.queryByText("Available capabilities")).not.toBeInTheDocument();
  });
});
