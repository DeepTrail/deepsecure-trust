import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import AgentDetailPage from "../page";
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

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "sdr-assistant-001" }),
}));

vi.mock("@/hooks/useSSE", () => ({
  useSSE: () => ({
    data: [],
    lastEvent: null,
    error: null,
    status: "disconnected",
    connected: false,
    clear: vi.fn(),
  }),
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
  }: {
    children: React.ReactNode;
    href: string;
  }) => <a href={href}>{children}</a>,
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

const mockApiClient = vi.mocked(apiClient);

const AGENT_INFO = {
  agent_id: "sdr-assistant-001",
  name: "SDR Assistant",
  lifecycle_state: "authenticated",
  status: "active",
};

const DELEGATIONS = [
  {
    delegation_id: "del-001",
    agent_id: "sdr-assistant-001",
    permissions: ["notion:pages:read", "slack:messages:write"],
    expires_in: 3600,
    created_at: "2026-05-06T10:00:00Z",
  },
];

const TOOLS_RESPONSE = {
  agent_id: "sdr-assistant-001",
  tools: [
    {
      name: "notion.search_pages",
      backend: "notion",
      permission: "notion:pages:read",
      available: true,
    },
    {
      name: "notion.create_page",
      backend: "notion",
      permission: "notion:pages:create",
      available: false,
      reason: "Not in delegation",
    },
  ],
};

const EVENTS_RESPONSE = [
  {
    id: "evt-1",
    tool_name: "notion.search_pages",
    status: "success",
    timestamp: "2026-05-06T12:00:00Z",
    details: "Found 3 pages",
  },
  {
    id: "evt-2",
    tool_name: "slack.post_message",
    status: "error",
    timestamp: "2026-05-06T11:55:00Z",
    details: "Rate limited",
  },
];

function mockSuccessfulFetch() {
  mockApiClient
    .mockResolvedValueOnce(AGENT_INFO)
    .mockResolvedValueOnce(DELEGATIONS)
    .mockResolvedValueOnce(TOOLS_RESPONSE)
    .mockResolvedValueOnce(EVENTS_RESPONSE)
    .mockResolvedValueOnce({ sessions: [], total: 0 })
    .mockResolvedValueOnce({ sessions: [], total: 0 });
}

describe("AgentDetailPage", () => {
  beforeEach(() => {
    mockApiClient.mockReset();
    mockApiClient.mockImplementation(() => Promise.resolve({ sessions: [], total: 0 }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows loading skeleton initially", () => {
    mockApiClient.mockReturnValue(new Promise(() => {}));
    render(<AgentDetailPage />);
    expect(screen.getByTestId("page-skeleton")).toBeInTheDocument();
  });

  it("renders agent name and ID in header", async () => {
    mockSuccessfulFetch();
    render(<AgentDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("SDR Assistant")).toBeInTheDocument();
    });
    expect(screen.getByText("sdr-assistant-001")).toBeInTheDocument();
  });

  it("renders LifecycleBadge with correct state", async () => {
    mockSuccessfulFetch();
    render(<AgentDetailPage />);

    await waitFor(() => {
      const badges = screen.getAllByText("Authenticated");
      expect(badges.length).toBeGreaterThan(0);
    });
  });

  it("renders LifecycleProgressBar step labels", async () => {
    mockSuccessfulFetch();
    render(<AgentDetailPage />);

    await waitFor(() => {
      expect(screen.getAllByText("Registered").length).toBeGreaterThan(0);
    });
    expect(screen.getAllByText("Delegated").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Authenticated").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Active").length).toBeGreaterThan(0);
  });

  it("renders Agent Integration section", async () => {
    mockSuccessfulFetch();
    render(<AgentDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("Agent Integration")).toBeInTheDocument();
    });
    expect(
      screen.getByText(/DEEPSECURE_AGENT_ID="sdr-assistant-001"/)
    ).toBeInTheDocument();
  });

  it("renders Session History section", async () => {
    mockSuccessfulFetch();
    render(<AgentDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("Session History")).toBeInTheDocument();
    });
  });

  it("renders delegated tools card with available tools from API", async () => {
    mockSuccessfulFetch();
    render(<AgentDetailPage />);

    await waitFor(() => {
      expect(screen.getByText(/Delegated Tools & Permissions/)).toBeInTheDocument();
    });

    expect(screen.getByText("search_pages")).toBeInTheDocument();
  });

  it("renders activity feed with events from API", async () => {
    mockSuccessfulFetch();
    render(<AgentDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("slack.post_message")).toBeInTheDocument();
    });

    expect(screen.getByText("Recent Activity (2)")).toBeInTheDocument();
  });

  it("calls 4 API endpoints on mount", async () => {
    mockSuccessfulFetch();
    render(<AgentDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("SDR Assistant")).toBeInTheDocument();
    });

    expect(mockApiClient).toHaveBeenCalledWith("agents/sdr-assistant-001");
    expect(mockApiClient).toHaveBeenCalledWith("auth/delegations");
    expect(mockApiClient).toHaveBeenCalledWith(
      "agents/sdr-assistant-001/tools"
    );
    expect(mockApiClient).toHaveBeenCalledWith(
      "audit/events?agent_id=sdr-assistant-001&limit=20"
    );
  });

  it("renders delegations section with permissions", async () => {
    mockSuccessfulFetch();
    render(<AgentDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("Delegations (1)")).toBeInTheDocument();
    });

    expect(screen.getByText("2 permissions")).toBeInTheDocument();
    expect(screen.getByText("del-001")).toBeInTheDocument();
  });

  it("shows 'No delegations' card when there are none", async () => {
    mockApiClient
      .mockResolvedValueOnce(AGENT_INFO)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce(TOOLS_RESPONSE)
      .mockResolvedValueOnce(EVENTS_RESPONSE)
      .mockResolvedValueOnce({ sessions: [], total: 0 })
      .mockResolvedValueOnce({ sessions: [], total: 0 });

    render(<AgentDetailPage />);

    await waitFor(() => {
      expect(
        screen.getByText("No delegations assigned")
      ).toBeInTheDocument();
    });
  });

  it("shows ErrorCard when API calls throw synchronously", async () => {
    mockApiClient.mockImplementation(() => {
      throw new ApiError(500, "Server Error");
    });

    render(<AgentDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });

    expect(
      screen.getByText("Failed to load agent data (500)")
    ).toBeInTheDocument();

    mockApiClient.mockReset();
  });

  it("retry button refetches data after error", async () => {
    mockApiClient.mockImplementation(() => {
      throw new ApiError(500, "Server Error");
    });

    render(<AgentDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });

    mockApiClient.mockReset();
    mockSuccessfulFetch();

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));

    await waitFor(() => {
      expect(screen.getByText(/Delegated Tools & Permissions/)).toBeInTheDocument();
    });
  });

  it("renders back link pointing to agents list", async () => {
    mockSuccessfulFetch();
    render(<AgentDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("SDR Assistant")).toBeInTheDocument();
    });

    const backLink = screen.getByText("Back").closest("a");
    expect(backLink).toHaveAttribute("href", "/dashboard/agents");
  });

  it("handles tools response with empty tools array", async () => {
    mockApiClient
      .mockResolvedValueOnce(AGENT_INFO)
      .mockResolvedValueOnce(DELEGATIONS)
      .mockResolvedValueOnce({ agent_id: "sdr-assistant-001", tools: [] })
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce({ sessions: [], total: 0 })
      .mockResolvedValueOnce({ sessions: [], total: 0 });

    render(<AgentDetailPage />);

    await waitFor(() => {
      expect(
        screen.getByText("No tools delegated yet")
      ).toBeInTheDocument();
    });

    expect(
      screen.getByText("No recent activity for this agent.")
    ).toBeInTheDocument();
  });

  it("handles events response in { events: [] } format", async () => {
    mockApiClient
      .mockResolvedValueOnce(AGENT_INFO)
      .mockResolvedValueOnce(DELEGATIONS)
      .mockResolvedValueOnce(TOOLS_RESPONSE)
      .mockResolvedValueOnce({ events: EVENTS_RESPONSE })
      .mockResolvedValueOnce({ sessions: [], total: 0 })
      .mockResolvedValueOnce({ sessions: [], total: 0 });

    render(<AgentDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("slack.post_message")).toBeInTheDocument();
    });
  });

  it("defaults to 'Registered' when agent has no lifecycle_state", async () => {
    mockApiClient
      .mockResolvedValueOnce({ agent_id: "sdr-assistant-001", name: "Agent" })
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce({ agent_id: "sdr-assistant-001", tools: [] })
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce({ sessions: [], total: 0 })
      .mockResolvedValueOnce({ sessions: [], total: 0 });

    render(<AgentDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("Agent")).toBeInTheDocument();
    });

    const registeredBadges = screen.getAllByText("Registered");
    expect(registeredBadges.length).toBeGreaterThan(0);
  });
});
