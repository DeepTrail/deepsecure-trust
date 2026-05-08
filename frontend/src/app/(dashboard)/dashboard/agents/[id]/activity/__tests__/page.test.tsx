import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { fireEvent } from "@testing-library/react";
import AgentActivityPage from "../page";
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
  useSSE: () => ({ data: [], lastEvent: null, error: null, status: "disconnected", connected: false, clear: vi.fn() }),
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

describe("AgentActivityPage", () => {
  beforeEach(() => {
    mockApiClient.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows loading skeleton initially", () => {
    mockApiClient.mockReturnValue(new Promise(() => {}));
    render(<AgentActivityPage />);
    expect(screen.getByTestId("page-skeleton")).toBeInTheDocument();
  });

  it("renders agent ID in the page header", async () => {
    mockApiClient
      .mockResolvedValueOnce(TOOLS_RESPONSE)
      .mockResolvedValueOnce(EVENTS_RESPONSE);

    render(<AgentActivityPage />);

    await waitFor(() => {
      expect(screen.getByText("sdr-assistant-001")).toBeInTheDocument();
    });
  });

  it("renders tools list with tools from API", async () => {
    mockApiClient
      .mockResolvedValueOnce(TOOLS_RESPONSE)
      .mockResolvedValueOnce(EVENTS_RESPONSE);

    render(<AgentActivityPage />);

    await waitFor(() => {
      expect(screen.getByText("Tools (2)")).toBeInTheDocument();
    });

    expect(screen.getByText("notion.create_page")).toBeInTheDocument();
    expect(screen.getByText("notion:pages:read")).toBeInTheDocument();
  });

  it("renders activity feed with events from API", async () => {
    mockApiClient
      .mockResolvedValueOnce(TOOLS_RESPONSE)
      .mockResolvedValueOnce(EVENTS_RESPONSE);

    render(<AgentActivityPage />);

    await waitFor(() => {
      expect(screen.getByText("slack.post_message")).toBeInTheDocument();
    });

    expect(screen.getByText("Recent Activity (2)")).toBeInTheDocument();
  });

  it("calls correct API endpoints with agent ID", async () => {
    mockApiClient
      .mockResolvedValueOnce(TOOLS_RESPONSE)
      .mockResolvedValueOnce(EVENTS_RESPONSE);

    render(<AgentActivityPage />);

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith(
        "agents/sdr-assistant-001/tools"
      );
      expect(mockApiClient).toHaveBeenCalledWith(
        "audit/events?agent_id=sdr-assistant-001&limit=20"
      );
    });
  });

  it("shows ErrorCard on API failure with status code", async () => {
    mockApiClient.mockRejectedValueOnce(new ApiError(404, "Not Found"));

    render(<AgentActivityPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });

    expect(
      screen.getByText("Failed to load agent data (404)")
    ).toBeInTheDocument();
  });

  it("shows generic error message for non-ApiError failures", async () => {
    mockApiClient.mockRejectedValueOnce(new Error("Network failure"));

    render(<AgentActivityPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });

    expect(
      screen.getByText("Failed to load agent data")
    ).toBeInTheDocument();
  });

  it("retry button refetches data", async () => {
    mockApiClient.mockRejectedValueOnce(new ApiError(500, "Server Error"));

    render(<AgentActivityPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });

    mockApiClient
      .mockResolvedValueOnce(TOOLS_RESPONSE)
      .mockResolvedValueOnce(EVENTS_RESPONSE);

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));

    await waitFor(() => {
      expect(screen.getByText("Tools (2)")).toBeInTheDocument();
    });
  });

  it("renders back link pointing to agents list", async () => {
    mockApiClient
      .mockResolvedValueOnce(TOOLS_RESPONSE)
      .mockResolvedValueOnce(EVENTS_RESPONSE);

    render(<AgentActivityPage />);

    await waitFor(() => {
      expect(screen.getByText("sdr-assistant-001")).toBeInTheDocument();
    });

    const backLink = screen.getByText("Back").closest("a");
    expect(backLink).toHaveAttribute("href", "/dashboard/agents");
  });

  it("handles tools response with empty tools array", async () => {
    mockApiClient
      .mockResolvedValueOnce({ agent_id: "sdr-assistant-001", tools: [] })
      .mockResolvedValueOnce([]);

    render(<AgentActivityPage />);

    await waitFor(() => {
      expect(
        screen.getByText("No tools configured for this agent.")
      ).toBeInTheDocument();
    });

    expect(
      screen.getByText("No recent activity for this agent.")
    ).toBeInTheDocument();
  });

  it("handles events response in { events: [] } format", async () => {
    mockApiClient
      .mockResolvedValueOnce(TOOLS_RESPONSE)
      .mockResolvedValueOnce({ events: EVENTS_RESPONSE });

    render(<AgentActivityPage />);

    await waitFor(() => {
      expect(screen.getByText("slack.post_message")).toBeInTheDocument();
    });
  });
});
