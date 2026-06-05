import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { SessionsTable } from "../SessionsTable";
import type { SessionSummary } from "@/lib/types/admin";

vi.mock("@/lib/api/client", () => ({
  apiClient: vi.fn(),
}));

import { apiClient } from "@/lib/api/client";
const mockApiClient = vi.mocked(apiClient);

const SESSIONS: SessionSummary[] = [
  {
    session_id: "asess-abc123def456",
    created_at: "2026-06-04T10:00:00Z",
    last_activity_at: "2026-06-04T12:00:00Z",
    delegator: "alice@acme.com",
    delegation_id: "del-1",
    tool_calls: 5,
    status: "active",
  },
  {
    session_id: "asess-xyz789000111",
    created_at: "2026-06-03T08:00:00Z",
    last_activity_at: "2026-06-03T09:00:00Z",
    delegator: "bob@acme.com",
    delegation_id: "del-2",
    tool_calls: 0,
    status: "expired",
  },
];

describe("SessionsTable", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders folded by default with session count", () => {
    render(<SessionsTable sessions={SESSIONS} agentId="agent-1" />);
    expect(screen.getByText("Sessions (2)")).toBeInTheDocument();
    expect(screen.queryByText("Delegator")).not.toBeInTheDocument();
  });

  it("shows preview of most recent session when folded", () => {
    render(<SessionsTable sessions={SESSIONS} agentId="agent-1" />);
    expect(screen.getByText(/Most recent:/)).toBeInTheDocument();
    expect(screen.getByText(/alice@acme.com/)).toBeInTheDocument();
  });

  it("opens the table on header click", () => {
    render(<SessionsTable sessions={SESSIONS} agentId="agent-1" />);
    fireEvent.click(screen.getByText("Sessions (2)"));
    expect(screen.getByText("Delegator")).toBeInTheDocument();
    expect(screen.getByText("Tool Calls")).toBeInTheDocument();
  });

  it("shows session data when opened", () => {
    render(<SessionsTable sessions={SESSIONS} agentId="agent-1" />);
    fireEvent.click(screen.getByText("Sessions (2)"));
    expect(screen.getByText("alice@acme.com")).toBeInTheDocument();
    expect(screen.getByText("bob@acme.com")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("0")).toBeInTheDocument();
  });

  it("shows active/expired status badges", () => {
    render(<SessionsTable sessions={SESSIONS} agentId="agent-1" />);
    fireEvent.click(screen.getByText("Sessions (2)"));
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("expired")).toBeInTheDocument();
  });

  it("lazy-loads events when expanding a session row", async () => {
    mockApiClient.mockResolvedValueOnce({
      events: [
        {
          id: "evt-1",
          tool: "notion.search_pages",
          event_type: "mcp_tool_call",
          success: true,
          timestamp: "2026-06-04T10:05:00Z",
          result_summary: "Found 3 pages",
        },
      ],
      total: 1,
    });

    render(<SessionsTable sessions={SESSIONS} agentId="agent-1" />);
    fireEvent.click(screen.getByText("Sessions (2)"));
    fireEvent.click(screen.getByText("alice@acme.com"));

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith(
        "admin/agents/agent-1/sessions/asess-abc123def456/events"
      );
    });

    await waitFor(() => {
      expect(screen.getByText("notion.search_pages")).toBeInTheDocument();
      expect(screen.getByText(/Found 3 pages/)).toBeInTheDocument();
    });
  });

  it("caches events and does not re-fetch", async () => {
    mockApiClient.mockResolvedValueOnce({ events: [], total: 0 });

    render(<SessionsTable sessions={SESSIONS} agentId="agent-1" />);
    fireEvent.click(screen.getByText("Sessions (2)"));
    fireEvent.click(screen.getByText("alice@acme.com"));

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledTimes(1);
    });

    // Collapse and re-expand
    fireEvent.click(screen.getByText("alice@acme.com"));
    fireEvent.click(screen.getByText("alice@acme.com"));

    // Should not have fetched again
    expect(mockApiClient).toHaveBeenCalledTimes(1);
  });

  it("shows empty state when no sessions", () => {
    render(<SessionsTable sessions={[]} agentId="agent-1" />);
    expect(screen.getByText("Sessions (0)")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Sessions (0)"));
    expect(screen.getByText("No sessions recorded")).toBeInTheDocument();
  });
});
