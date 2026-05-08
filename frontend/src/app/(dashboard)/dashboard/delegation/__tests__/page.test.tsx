import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import DelegationPage from "../page";
import { apiClient, ApiError } from "@/lib/api/client";

vi.mock("@/lib/api/client", () => ({
  apiClient: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number;
    statusText: string;
    body?: unknown;
    constructor(status: number, statusText: string, body?: unknown) {
      super(`API error: ${status} ${statusText}`);
      this.name = "ApiError";
      this.status = status;
      this.statusText = statusText;
      this.body = body;
    }
  },
}));

vi.mock("@/components/feedback/page-skeleton", () => ({
  PageSkeleton: () => <div data-testid="page-skeleton">Loading...</div>,
}));

vi.mock("@/components/feedback/error-card", () => ({
  ErrorCard: ({
    title,
    message,
    retry,
  }: {
    title: string;
    message: string;
    retry: () => void;
  }) => (
    <div data-testid="error-card">
      <span>{title}</span>
      <span>{message}</span>
      <button onClick={retry}>Retry</button>
    </div>
  ),
}));

vi.mock("@/components/feedback/empty-state", () => ({
  EmptyState: ({
    title,
    description,
  }: {
    title: string;
    description?: string;
  }) => (
    <div data-testid="empty-state">
      <span>{title}</span>
      {description && <span>{description}</span>}
    </div>
  ),
}));

vi.mock("@/components/delegation/DelegationBuilder", () => ({
  DelegationBuilder: ({
    agents,
    permissions,
  }: {
    agents: unknown[];
    permissions: unknown[];
  }) => (
    <div data-testid="delegation-builder">
      <span>agents: {agents.length}</span>
      <span>permissions: {permissions.length}</span>
    </div>
  ),
}));

const mockApiClient = vi.mocked(apiClient);

const AGENTS = [
  { agent_id: "agent-1", name: "Alpha Agent" },
  { agent_id: "agent-2", name: "Beta Agent" },
];

const PERMISSIONS = {
  permissions: [
    { id: "p1", service: "notion", scope: "pages", action: "read", locked: false },
    { id: "p2", service: "github", scope: "repos", action: "read", locked: false },
  ],
};

describe("DelegationPage", () => {
  beforeEach(() => {
    mockApiClient.mockReset();
  });

  it("shows loading skeleton initially", () => {
    mockApiClient.mockReturnValue(new Promise(() => {}));
    render(<DelegationPage />);
    expect(screen.getByTestId("page-skeleton")).toBeInTheDocument();
  });

  it("renders DelegationBuilder when data loads successfully", async () => {
    mockApiClient
      .mockResolvedValueOnce(AGENTS)
      .mockResolvedValueOnce(PERMISSIONS);

    render(<DelegationPage />);

    await waitFor(() => {
      expect(screen.getByTestId("delegation-builder")).toBeInTheDocument();
    });
    expect(screen.getByText("agents: 2")).toBeInTheDocument();
    expect(screen.getByText("permissions: 2")).toBeInTheDocument();
  });

  it("shows page title and description when loaded", async () => {
    mockApiClient
      .mockResolvedValueOnce(AGENTS)
      .mockResolvedValueOnce(PERMISSIONS);

    render(<DelegationPage />);

    await waitFor(() => {
      expect(screen.getByText("Delegation")).toBeInTheDocument();
    });
    expect(
      screen.getByText(/grant granular permissions/i),
    ).toBeInTheDocument();
  });

  it("shows empty state when no agents are registered", async () => {
    mockApiClient
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce(PERMISSIONS);

    render(<DelegationPage />);

    await waitFor(() => {
      expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    });
    expect(screen.getByText("No agents available")).toBeInTheDocument();
  });

  it("shows ErrorCard on API failure", async () => {
    mockApiClient.mockRejectedValueOnce(
      new ApiError(500, "Server Error"),
    );

    render(<DelegationPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });
    expect(
      screen.getByText("Failed to load delegation data (500)"),
    ).toBeInTheDocument();
  });

  it("shows generic error for non-ApiError failures", async () => {
    mockApiClient.mockRejectedValueOnce(new Error("Network failure"));

    render(<DelegationPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });
    expect(
      screen.getByText("Failed to load delegation data"),
    ).toBeInTheDocument();
  });

  it("handles agents in object format with .agents property", async () => {
    mockApiClient
      .mockResolvedValueOnce({ agents: AGENTS })
      .mockResolvedValueOnce(PERMISSIONS);

    render(<DelegationPage />);

    await waitFor(() => {
      expect(screen.getByTestId("delegation-builder")).toBeInTheDocument();
    });
    expect(screen.getByText("agents: 2")).toBeInTheDocument();
  });

  it("retries data fetch when retry button is clicked", async () => {
    mockApiClient.mockRejectedValueOnce(new ApiError(500, "Server Error"));

    render(<DelegationPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });

    mockApiClient
      .mockResolvedValueOnce(AGENTS)
      .mockResolvedValueOnce(PERMISSIONS);

    const retryBtn = screen.getByRole("button", { name: /retry/i });
    retryBtn.click();

    await waitFor(() => {
      expect(screen.getByTestId("delegation-builder")).toBeInTheDocument();
    });
  });
});
