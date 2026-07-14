import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import App from "../src/App.jsx";

// Mock the API layer so unit tests run deterministically with no network.
vi.mock("../src/api.js", () => ({
  getWorkflows: vi.fn(),
  createWorkflow: vi.fn(),
  runWorkflow: vi.fn(),
  getStatus: vi.fn(),
  controlInstance: vi.fn(),
  getSchedules: vi.fn(),
  createSchedule: vi.fn(),
  deleteSchedule: vi.fn(),
  esc: (s) => String(s ?? ""),
}));

import * as api from "../src/api.js";

beforeEach(() => {
  vi.clearAllMocks();
  api.getWorkflows.mockResolvedValue([]);
});

describe("Control Center <App/>", () => {
  it("renders the application shell (smoke)", () => {
    render(<App />);
    expect(screen.getByText("Control Center")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Workflows" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Instances" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Schedules" })).toBeInTheDocument();
  });

  it("switches between tabs", async () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Instances" }));
    expect(await screen.findByText(/No instances yet/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Schedules" }));
    expect(await screen.findByText(/No schedules yet/i)).toBeInTheDocument();
  });

  it("lists workflows returned by the mocked API", async () => {
    api.getWorkflows.mockResolvedValue([
      { name: "deploy", description: "ship it" },
      { name: "report", description: "daily summary" },
    ]);
    render(<App />);
    expect(await screen.findByText("deploy")).toBeInTheDocument();
    expect(screen.getByText("ship it")).toBeInTheDocument();
    expect(screen.getByText("report")).toBeInTheDocument();
  });

  it("shows an error state when the API fails", async () => {
    api.getWorkflows.mockRejectedValue(new Error("boom"));
    render(<App />);
    await waitFor(() =>
      expect(screen.getByText(/Failed to load workflows: boom/i)).toBeInTheDocument()
    );
  });
});
