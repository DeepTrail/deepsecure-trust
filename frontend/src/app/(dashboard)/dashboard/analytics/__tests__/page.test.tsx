import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

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
    names: new Map([["agent-001", "SDR Agent"]]),
    loading: false,
    resolve: (id: string) =>
      id === "agent-001" ? "SDR Agent" : id,
  }),
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

vi.mock("@/components/charts/DelegationChainFlow", () => ({
  __esModule: true,
  default: ({
    userEmail,
    connectedServices,
    delegations,
  }: {
    userEmail: string;
    connectedServices: { services: Record<string, unknown> };
    delegations: unknown[];
  }) => (
    <div data-testid="delegation-chain-flow">
      <span>Delegation Chain</span>
      <span data-testid="chain-user">{userEmail}</span>
      <span data-testid="chain-services">
        {Object.keys(connectedServices.services).length} services
      </span>
      <span data-testid="chain-delegations">
        {delegations.length} delegations
      </span>
    </div>
  ),
}));

import AnalyticsPage from "../page";
import { apiClient } from "@/lib/api/client";

const mockApiClient = vi.mocked(apiClient);

const mockSummary = {
  total_events: 150,
  by_event_type: { mcp_tool_call: 145, permission_denied: 5 },
  by_tool: {
    "notion.search_pages": 50,
    "notion.read_page": 30,
    "slack.post_message": 20,
  },
  by_agent: { "agent-001": 100, "agent-002": 50 },
  time_range: { start: "2026-05-20T00:00:00Z", end: "2026-05-26T23:59:59Z" },
};

const mockDenials = {
  events: [
    {
      id: "evt-d1",
      timestamp: "2026-05-26T15:55:00Z",
      event_type: "permission_denied",
      agent_id: "agent-001",
      on_behalf_of: "sarah@acme.com",
      organization_id: null,
      tool: null,
      success: false,
      arguments: null,
      result_summary: null,
      reason: "Permission not delegated",
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
  total: 1,
  limit: 500,
  offset: 0,
};

const mockDelegations = [
  {
    delegation_id: "del-001",
    agent_id: "agent-001",
    permissions: ["notion:pages:search", "notion:pages:read"],
  },
];

const mockServices = {
  services: {
    notion: {
      connected: true,
      service_name: "Notion",
      scopes_granted: ["read_content", "update_content"],
      available_permissions: [
        "notion:pages:search",
        "notion:pages:read",
        "notion:pages:update",
      ],
      connected_at: "2026-05-20T04:58:51Z",
    },
    slack: {
      connected: true,
      service_name: "Slack",
      scopes_granted: ["channels:read"],
      available_permissions: ["slack:channels:list"],
      connected_at: "2026-05-20T05:00:00Z",
    },
  },
  all_permissions: [
    "notion:pages:search",
    "notion:pages:read",
    "notion:pages:update",
    "slack:channels:list",
  ],
  total_services: 2,
  total_permissions: 4,
};

const mockProfile = { email: "test@acme.com", user_id: "test@acme.com" };

function mockApiSuccess() {
  mockApiClient.mockImplementation(((path: string) => {
    if (path.includes("audit/summary")) return Promise.resolve(mockSummary);
    if (path.includes("audit/events")) return Promise.resolve(mockDenials);
    if (path.includes("auth/delegations"))
      return Promise.resolve(mockDelegations);
    if (path.includes("users/me/available-permissions"))
      return Promise.resolve(mockServices);
    if (path.includes("users/me")) return Promise.resolve(mockProfile);
    return Promise.resolve([]);
  }) as typeof apiClient);
}

describe("AnalyticsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading skeleton initially", () => {
    mockApiClient.mockReturnValue(new Promise(() => {}) as never);
    render(<AnalyticsPage />);
    expect(screen.getByTestId("page-skeleton")).toBeInTheDocument();
  });

  it("renders page title", async () => {
    mockApiSuccess();
    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText("Tool Call Analytics")).toBeInTheDocument();
    });
  });

  it("renders metrics cards with correct values", async () => {
    mockApiSuccess();
    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText("150")).toBeInTheDocument();
    });

    expect(screen.getByText("Total Events")).toBeInTheDocument();
    expect(screen.getByText("Unique Tools")).toBeInTheDocument();
    expect(screen.getByText("Active Agents")).toBeInTheDocument();
    expect(screen.getByText("Denial Rate")).toBeInTheDocument();
  });

  it("renders volume by backend section", async () => {
    mockApiSuccess();
    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText("Volume by Backend")).toBeInTheDocument();
    });

    expect(screen.getByText("notion")).toBeInTheDocument();
    expect(screen.getByText("slack")).toBeInTheDocument();
  });

  it("renders top tools table", async () => {
    mockApiSuccess();
    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText("Top Tools")).toBeInTheDocument();
    });

    expect(screen.getByText("notion.search_pages")).toBeInTheDocument();
    expect(screen.getByText("notion.read_page")).toBeInTheDocument();
    expect(screen.getByText("slack.post_message")).toBeInTheDocument();
  });

  it("renders denial analysis section", async () => {
    mockApiSuccess();
    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("Permission Denial Analysis")
      ).toBeInTheDocument();
    });

    expect(screen.getByText("slack:messages:send")).toBeInTheDocument();
    expect(screen.getByText("1 denials")).toBeInTheDocument();
  });

  it("renders agent permission utilization table", async () => {
    mockApiSuccess();
    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("Agent Permission Utilization")
      ).toBeInTheDocument();
    });

    expect(screen.getByText("SDR Agent")).toBeInTheDocument();
  });

  it("renders delegation chain flow section", async () => {
    mockApiSuccess();
    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(
        screen.getByTestId("delegation-chain-flow")
      ).toBeInTheDocument();
    });

    expect(screen.getByText("Delegation Chain")).toBeInTheDocument();
  });

  it("passes correct data to delegation chain flow", async () => {
    mockApiSuccess();
    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("chain-user")).toHaveTextContent(
        "test@acme.com"
      );
    });

    expect(screen.getByTestId("chain-services")).toHaveTextContent(
      "2 services"
    );
    expect(screen.getByTestId("chain-delegations")).toHaveTextContent(
      "1 delegations"
    );
  });

  it("shows ErrorCard on API failure", async () => {
    mockApiClient.mockRejectedValue(new Error("Network error"));
    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });

    expect(
      screen.getByText("Failed to load analytics data")
    ).toBeInTheDocument();
  });
});
