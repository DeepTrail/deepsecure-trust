import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { SessionHistoryTable } from "../SessionHistoryTable";
import { apiClient } from "@/lib/api/client";

vi.mock("@/lib/api/client", () => ({
  apiClient: vi.fn(),
}));

const mockApiClient = vi.mocked(apiClient);

const SESSIONS = [
  {
    session_id: "sess-aabb0011-active-session",
    agent_id: "agent-1",
    delegation_id: "del-1",
    is_active: true,
    source_ip: "192.168.1.1",
    created_at: "2026-05-06T12:00:00Z",
    expires_at: "2026-05-06T13:00:00Z",
    last_activity_at: "2026-05-06T12:30:00Z",
  },
  {
    session_id: "sess-ffgg0022-expired-session",
    agent_id: "agent-1",
    delegation_id: "del-2",
    is_active: false,
    source_ip: null,
    created_at: "2026-05-05T10:00:00Z",
    expires_at: "2026-05-05T11:00:00Z",
    last_activity_at: null,
  },
];

describe("SessionHistoryTable", () => {
  beforeEach(() => {
    mockApiClient.mockReset();
  });

  it("shows loading skeletons initially", () => {
    mockApiClient.mockReturnValue(new Promise(() => {}));
    const { container } = render(<SessionHistoryTable agentId="agent-1" />);

    expect(screen.getByText("Session History")).toBeInTheDocument();
    const skeletons = container.querySelectorAll('[class*="animate-pulse"], [data-slot="skeleton"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("calls the sessions API with correct agent ID", async () => {
    mockApiClient.mockResolvedValueOnce({ sessions: [], total: 0 });
    render(<SessionHistoryTable agentId="test-agent-99" />);

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith("agents/test-agent-99/sessions");
    });
  });

  it("renders sessions with paginated response format", async () => {
    mockApiClient.mockResolvedValueOnce({
      sessions: SESSIONS,
      total: 2,
    });

    render(<SessionHistoryTable agentId="agent-1" />);

    await waitFor(() => {
      expect(screen.getByText("2 total")).toBeInTheDocument();
    });

    expect(screen.getByText(/sess-aabb00/)).toBeInTheDocument();
    expect(screen.getByText(/sess-ffgg00/)).toBeInTheDocument();
  });

  it("renders sessions with array response format", async () => {
    mockApiClient.mockResolvedValueOnce(SESSIONS);

    render(<SessionHistoryTable agentId="agent-1" />);

    await waitFor(() => {
      expect(screen.getByText("2 total")).toBeInTheDocument();
    });
  });

  it("shows 'Valid' badge on active sessions", async () => {
    mockApiClient.mockResolvedValueOnce({ sessions: SESSIONS, total: 2 });
    render(<SessionHistoryTable agentId="agent-1" />);

    await waitFor(() => {
      expect(screen.getByText("Valid")).toBeInTheDocument();
    });
  });

  it("shows source IP when present", async () => {
    mockApiClient.mockResolvedValueOnce({ sessions: SESSIONS, total: 2 });
    render(<SessionHistoryTable agentId="agent-1" />);

    await waitFor(() => {
      expect(screen.getByText("192.168.1.1")).toBeInTheDocument();
    });
  });

  it("shows empty state when no sessions exist", async () => {
    mockApiClient.mockResolvedValueOnce({ sessions: [], total: 0 });
    render(<SessionHistoryTable agentId="agent-1" />);

    await waitFor(() => {
      expect(
        screen.getByText("No sessions recorded yet.")
      ).toBeInTheDocument();
    });
  });

  it("shows error message on API failure", async () => {
    mockApiClient.mockRejectedValueOnce(new Error("Network error"));
    render(<SessionHistoryTable agentId="agent-1" />);

    await waitFor(() => {
      expect(
        screen.getByText("Failed to load sessions")
      ).toBeInTheDocument();
    });
  });

  it("applies active session styling", async () => {
    mockApiClient.mockResolvedValueOnce({
      sessions: [SESSIONS[0]],
      total: 1,
    });

    const { container } = render(<SessionHistoryTable agentId="agent-1" />);

    await waitFor(() => {
      expect(screen.getByText(/sess-aabb00/)).toBeInTheDocument();
    });

    const sessionRow = container.querySelector(".border-primary\\/30");
    expect(sessionRow).toBeTruthy();
  });
});
