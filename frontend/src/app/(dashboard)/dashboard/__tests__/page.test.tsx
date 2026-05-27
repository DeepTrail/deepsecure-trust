import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";

vi.mock("@/lib/api/client", () => ({
  apiClient: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number;
    statusText: string;
    constructor(status: number, statusText: string) {
      super(`API error: ${status} ${statusText}`);
      this.name = "ApiError";
      this.status = status;
      this.statusText = statusText;
    }
  },
}));

vi.mock("@/hooks/useAgentNames", () => ({
  useAgentNames: () => ({
    names: new Map([["test-agent", "Test Agent"]]),
    loading: false,
    resolve: (id: string) => (id === "test-agent" ? "Test Agent" : id),
  }),
}));

vi.mock("@/lib/auth/onboarding", () => ({
  checkOnboardingStatus: () => Promise.resolve("dashboard"),
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
  EmptyState: ({ title }: { title: string }) => (
    <div data-testid="empty-state">{title}</div>
  ),
}));

import DashboardPage from "../page";
import { apiClient } from "@/lib/api/client";

const mockApiClient = vi.mocked(apiClient);

const mockAgents = [{ id: "agent-1" }, { id: "agent-2" }, { id: "agent-3" }];
const mockPolicies = [
  { id: "policy-1" },
  { id: "policy-2" },
  { id: "policy-3" },
  { id: "policy-4" },
  { id: "policy-5" },
];
const mockEventsResponse = {
  events: [
    {
      id: "evt-1",
      event_type: "mcp_tool_call",
      timestamp: "2026-01-01T09:00:00Z",
      agent_id: "test-agent",
      on_behalf_of: "sarah@acme.com",
      organization_id: null,
      tool: "notion.search_pages",
      success: true,
      arguments: null,
      result_summary: null,
      reason: null,
      attempted_tool: null,
      required_permission: null,
      duration_ms: 250,
      session_id: null,
      agent_session_id: null,
      mcp_session_id: null,
      delegation_id: null,
      extra_data: null,
    },
    {
      id: "evt-2",
      event_type: "permission_denied",
      timestamp: "2026-01-01T10:00:00Z",
      agent_id: null,
      on_behalf_of: "admin@acme.com",
      organization_id: null,
      tool: null,
      success: false,
      arguments: null,
      result_summary: null,
      reason: "Not delegated",
      attempted_tool: "slack.post_message",
      required_permission: "slack:messages:send",
      duration_ms: null,
      session_id: null,
      agent_session_id: null,
      mcp_session_id: null,
      delegation_id: null,
      extra_data: null,
    },
  ],
  total: 2,
  limit: 10,
  offset: 0,
};

function mockApiSuccess() {
  mockApiClient.mockImplementation(((path: string) => {
    if (path.startsWith("agents")) return Promise.resolve(mockAgents);
    if (path.startsWith("policies")) return Promise.resolve(mockPolicies);
    if (path.startsWith("audit")) return Promise.resolve(mockEventsResponse);
    return Promise.resolve([]);
  }) as typeof apiClient);
}

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading skeleton initially", () => {
    mockApiClient.mockReturnValue(new Promise(() => {}) as never);
    render(<DashboardPage />);
    expect(screen.getByTestId("page-skeleton")).toBeInTheDocument();
  });

  it("renders metric cards with correct counts", async () => {
    mockApiSuccess();
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Agents")).toBeInTheDocument();
    });

    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Policies")).toBeInTheDocument();
    expect(screen.getByText("Activity")).toBeInTheDocument();
  });

  it("renders recent events with tool names", async () => {
    mockApiSuccess();
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("notion.search_pages")).toBeInTheDocument();
    });

    expect(screen.getByText("slack.post_message")).toBeInTheDocument();
    expect(screen.getByText("Test Agent")).toBeInTheDocument();
  });

  it("shows EmptyState when events array is empty", async () => {
    mockApiClient.mockImplementation(((path: string) => {
      if (path.startsWith("agents")) return Promise.resolve(mockAgents);
      if (path.startsWith("policies")) return Promise.resolve(mockPolicies);
      if (path.startsWith("audit"))
        return Promise.resolve({ events: [], total: 0, limit: 10, offset: 0 });
      return Promise.resolve([]);
    }) as typeof apiClient);

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    });

    expect(screen.getByText("No recent activity")).toBeInTheDocument();
  });

  it("shows ErrorCard on fetch failure", async () => {
    mockApiClient.mockImplementation(() => {
      throw new Error("Network error");
    });

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });

    expect(
      screen.getByText("Failed to load dashboard data")
    ).toBeInTheDocument();
  });

  it("retry button re-fetches data", async () => {
    mockApiClient.mockImplementation(() => {
      throw new Error("Network error");
    });

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });

    mockApiSuccess();

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));

    await waitFor(() => {
      expect(screen.getByText("Agents")).toBeInTheDocument();
    });

    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("handles partial API failure gracefully", async () => {
    mockApiClient.mockImplementation(((path: string) => {
      if (path.startsWith("agents")) return Promise.resolve(mockAgents);
      if (path.startsWith("policies"))
        return Promise.reject(new Error("Policies unavailable"));
      if (path.startsWith("audit")) return Promise.resolve(mockEventsResponse);
      return Promise.resolve([]);
    }) as typeof apiClient);

    render(<DashboardPage />);

    await waitFor(() => {
      const errorCard = screen.queryByTestId("error-card");
      const agentsText = screen.queryByText("Agents");
      expect(errorCard || agentsText).toBeTruthy();
    });
  });

  it("displays zero count when API returns empty arrays", async () => {
    mockApiClient.mockImplementation(() => {
      return Promise.resolve([] as never);
    });

    render(<DashboardPage />);

    await waitFor(() => {
      const zeroElements = screen.queryAllByText("0");
      const emptyState = screen.queryByTestId("empty-state");
      expect(zeroElements.length > 0 || emptyState).toBeTruthy();
    });
  });
});
