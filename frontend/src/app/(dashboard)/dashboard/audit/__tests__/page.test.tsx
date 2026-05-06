import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  render,
  screen,
  waitFor,
  fireEvent,
} from "@testing-library/react";

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

import AuditPage from "../page";
import { apiClient } from "@/lib/api/client";

const mockApiClient = vi.mocked(apiClient);

const mockEvents = [
  {
    id: "evt-1",
    event_type: "mcp_tool_call",
    token_layer: "agent",
    agent_id: "test-agent",
    user_id: null,
    timestamp: "2026-01-01T09:00:00Z",
    details: { tool: "notion.search_pages" },
    attribution_chain: [
      {
        actor_type: "user",
        actor_id: "user@test.com",
        action: "delegated",
        timestamp: "2026-01-01T08:00:00Z",
      },
      {
        actor_type: "agent",
        actor_id: "test-agent",
        action: "tool_call",
        timestamp: "2026-01-01T09:00:00Z",
      },
    ],
  },
  {
    id: "evt-2",
    event_type: "sso_login",
    token_layer: "user",
    agent_id: null,
    user_id: "admin@acme.com",
    timestamp: "2026-01-01T10:00:00Z",
    details: { idp: "okta" },
    attribution_chain: [],
  },
];

function mockApiSuccess(events = mockEvents) {
  mockApiClient.mockResolvedValue(events as never);
}

describe("AuditPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading skeleton initially", () => {
    mockApiClient.mockReturnValue(new Promise(() => {}) as never);
    render(<AuditPage />);
    expect(screen.getByTestId("page-skeleton")).toBeInTheDocument();
  });

  it("renders event list with token layer badges", async () => {
    mockApiSuccess();
    render(<AuditPage />);

    await waitFor(() => {
      expect(screen.getByText("Audit Trail")).toBeInTheDocument();
    });

    expect(screen.getAllByText("agent").length).toBeGreaterThan(0);
    expect(screen.getAllByText("user").length).toBeGreaterThan(0);
    expect(screen.getAllByText("mcp_tool_call").length).toBeGreaterThan(0);
    expect(screen.getAllByText("sso_login").length).toBeGreaterThan(0);
  });

  it("shows ErrorCard on API failure", async () => {
    mockApiClient.mockRejectedValue(new Error("Network error"));
    render(<AuditPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });

    expect(
      screen.getByText("Failed to load audit events")
    ).toBeInTheDocument();
  });

  it("shows EmptyState when no events", async () => {
    mockApiSuccess([]);
    render(<AuditPage />);

    await waitFor(() => {
      expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    });

    expect(screen.getByText("No audit events")).toBeInTheDocument();
  });

  it("clicking event shows detail panel", async () => {
    mockApiSuccess();
    render(<AuditPage />);

    await waitFor(() => {
      expect(screen.getByText("Audit Trail")).toBeInTheDocument();
    });

    const agentLabel = screen.getByText("Agent: test-agent");
    const eventCard = agentLabel.closest("[class*='cursor-pointer']")!;
    fireEvent.click(eventCard);

    await waitFor(() => {
      expect(screen.getByText("Event Details")).toBeInTheDocument();
    });

    expect(screen.getByText("Metadata")).toBeInTheDocument();
    expect(screen.getByText("notion.search_pages")).toBeInTheDocument();
  });

  it("detail panel shows attribution chain", async () => {
    mockApiSuccess();
    render(<AuditPage />);

    await waitFor(() => {
      expect(screen.getByText("Audit Trail")).toBeInTheDocument();
    });

    const agentLabel = screen.getByText("Agent: test-agent");
    fireEvent.click(agentLabel.closest("[class*='cursor-pointer']")!);

    await waitFor(() => {
      expect(screen.getByText("Attribution Chain")).toBeInTheDocument();
    });

    expect(screen.getByText("user@test.com")).toBeInTheDocument();
    expect(screen.getByText(/delegated —/)).toBeInTheDocument();
    expect(screen.getByText(/tool_call —/)).toBeInTheDocument();
  });

  it("closing detail panel hides it", async () => {
    mockApiSuccess();
    render(<AuditPage />);

    await waitFor(() => {
      expect(screen.getByText("Audit Trail")).toBeInTheDocument();
    });

    const agentLabel = screen.getByText("Agent: test-agent");
    fireEvent.click(agentLabel.closest("[class*='cursor-pointer']")!);

    await waitFor(() => {
      expect(screen.getByText("Event Details")).toBeInTheDocument();
    });

    const detailTitle = screen.getByText("Event Details");
    const cardHeader = detailTitle.parentElement!;
    const closeButton = cardHeader.querySelector("button")!;
    fireEvent.click(closeButton);

    await waitFor(() => {
      expect(screen.queryByText("Event Details")).not.toBeInTheDocument();
    });
  });

  it("filter controls update query", async () => {
    mockApiSuccess();
    render(<AuditPage />);

    await waitFor(() => {
      expect(screen.getByText("Audit Trail")).toBeInTheDocument();
    });

    const eventTypeSelect = screen.getByLabelText("Event Type");
    fireEvent.change(eventTypeSelect, { target: { value: "mcp_tool_call" } });

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith(
        expect.stringContaining("event_type=mcp_tool_call")
      );
    });
  });

  it("clear filters button resets all filters", async () => {
    mockApiSuccess();
    render(<AuditPage />);

    await waitFor(() => {
      expect(screen.getByText("Audit Trail")).toBeInTheDocument();
    });

    const eventTypeSelect = screen.getByLabelText("Event Type");
    fireEvent.change(eventTypeSelect, { target: { value: "mcp_tool_call" } });

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /clear filters/i })
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /clear filters/i }));

    await waitFor(() => {
      expect(
        screen.queryByRole("button", { name: /clear filters/i })
      ).not.toBeInTheDocument();
    });
  });

  it("pagination shows Previous and Next buttons", async () => {
    mockApiSuccess();
    render(<AuditPage />);

    await waitFor(() => {
      expect(screen.getByText("Audit Trail")).toBeInTheDocument();
    });

    expect(
      screen.getByRole("button", { name: /previous/i })
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /next/i })).toBeInTheDocument();
    expect(screen.getByText("Page 1")).toBeInTheDocument();

    expect(screen.getByRole("button", { name: /previous/i })).toBeDisabled();
  });

  it("shows ApiError with status code on fetch failure", async () => {
    const { ApiError: MockApiError } = await import("@/lib/api/client");
    mockApiClient.mockRejectedValue(
      new MockApiError(403, "Forbidden") as never
    );
    render(<AuditPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });

    expect(
      screen.getByText("Failed to load audit events (403)")
    ).toBeInTheDocument();
  });

  it("retry button calls fetchEvents again", async () => {
    mockApiClient.mockRejectedValue(new Error("Network error") as never);

    render(<AuditPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });

    const callCount = mockApiClient.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));

    await waitFor(() => {
      expect(mockApiClient.mock.calls.length).toBeGreaterThan(callCount);
    });
  });

  it("displays agent_id and user_id on event cards", async () => {
    mockApiSuccess();
    render(<AuditPage />);

    await waitFor(() => {
      expect(screen.getByText("Audit Trail")).toBeInTheDocument();
    });

    expect(screen.getByText("Agent: test-agent")).toBeInTheDocument();
    expect(screen.getByText("User: admin@acme.com")).toBeInTheDocument();
  });
});
