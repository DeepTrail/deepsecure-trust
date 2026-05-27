import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  render,
  screen,
  waitFor,
  fireEvent,
} from "@testing-library/react";
import type { AuditEvent } from "@/lib/types/audit";

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

function makeEvent(overrides: Partial<AuditEvent> = {}): AuditEvent {
  return {
    id: "evt-1",
    timestamp: "2026-01-01T09:00:00Z",
    event_type: "mcp_tool_call",
    agent_id: "test-agent",
    on_behalf_of: "sarah@acme.com",
    organization_id: null,
    tool: "notion.search_pages",
    success: true,
    arguments: { query: "meeting notes" },
    result_summary: "Found 5 results",
    reason: null,
    attempted_tool: null,
    required_permission: null,
    duration_ms: 473,
    session_id: "sess-001",
    agent_session_id: "asess-001",
    mcp_session_id: "mcpsess-001",
    delegation_id: "del-001",
    extra_data: null,
    ...overrides,
  };
}

const mockEvents: AuditEvent[] = [
  makeEvent({
    id: "evt-1",
    tool: "notion.search_pages",
    success: true,
    duration_ms: 473,
  }),
  makeEvent({
    id: "evt-2",
    event_type: "permission_denied",
    tool: null,
    success: false,
    attempted_tool: "slack.post_message",
    required_permission: "slack:messages:send",
    duration_ms: null,
    timestamp: "2026-01-01T10:00:00Z",
  }),
];

function mockApiSuccess(events = mockEvents) {
  mockApiClient.mockResolvedValue({
    events,
    total: events.length,
    limit: 20,
    offset: 0,
  } as never);
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

  it("renders event list with tool names", async () => {
    mockApiSuccess();
    render(<AuditPage />);

    await waitFor(() => {
      expect(screen.getByText("Audit Trail")).toBeInTheDocument();
    });

    expect(screen.getByText("notion.search_pages")).toBeInTheDocument();
    expect(screen.getByText("slack.post_message")).toBeInTheDocument();
  });

  it("shows success/error icons", async () => {
    mockApiSuccess();
    render(<AuditPage />);

    await waitFor(() => {
      expect(screen.getByText("Audit Trail")).toBeInTheDocument();
    });

    const checkIcons = document.querySelectorAll(".lucide-circle-check");
    const xIcons = document.querySelectorAll(".lucide-circle-x");
    expect(checkIcons.length).toBeGreaterThan(0);
    expect(xIcons.length).toBeGreaterThan(0);
  });

  it("displays agent names via useAgentNames", async () => {
    mockApiSuccess();
    render(<AuditPage />);

    await waitFor(() => {
      expect(screen.getByText("notion.search_pages")).toBeInTheDocument();
    });

    expect(screen.getAllByText("Test Agent").length).toBeGreaterThan(0);
  });

  it("shows duration for tool calls", async () => {
    mockApiSuccess();
    render(<AuditPage />);

    await waitFor(() => {
      expect(screen.getByText("473ms")).toBeInTheDocument();
    });
  });

  it("shows DENIED prefix for permission_denied events", async () => {
    mockApiSuccess();
    render(<AuditPage />);

    await waitFor(() => {
      expect(
        screen.getByText("DENIED: slack:messages:send")
      ).toBeInTheDocument();
    });
  });

  it("shows event type badges", async () => {
    mockApiSuccess();
    render(<AuditPage />);

    await waitFor(() => {
      expect(screen.getByText("Audit Trail")).toBeInTheDocument();
    });

    expect(screen.getAllByText("mcp_tool_call").length).toBeGreaterThan(0);
    expect(screen.getAllByText("permission_denied").length).toBeGreaterThan(0);
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

  it("expands event detail on click", async () => {
    mockApiSuccess();
    render(<AuditPage />);

    await waitFor(() => {
      expect(screen.getByText("notion.search_pages")).toBeInTheDocument();
    });

    const eventButton = screen.getByText("notion.search_pages").closest("button");
    if (eventButton) {
      fireEvent.click(eventButton);

      await waitFor(() => {
        expect(screen.getByText(/Arguments:/)).toBeInTheDocument();
      });
    }
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

  it("tool filter is present", async () => {
    mockApiSuccess();
    render(<AuditPage />);

    await waitFor(() => {
      expect(screen.getByText("Audit Trail")).toBeInTheDocument();
    });

    expect(screen.getByLabelText("Tool")).toBeInTheDocument();
  });

  it("user filter is present", async () => {
    mockApiSuccess();
    render(<AuditPage />);

    await waitFor(() => {
      expect(screen.getByText("Audit Trail")).toBeInTheDocument();
    });

    expect(screen.getByLabelText("User")).toBeInTheDocument();
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
});
