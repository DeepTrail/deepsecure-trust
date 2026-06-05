import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { IdentityStackPanel } from "../IdentityStackPanel";
import type { IdentityStackResponse } from "@/lib/types/admin";

vi.mock("@/lib/api/client", () => ({
  apiClient: vi.fn(),
}));

import { apiClient } from "@/lib/api/client";
const mockApiClient = vi.mocked(apiClient);

const MOCK_RESPONSE: IdentityStackResponse = {
  agent_id: "agent-test-001",
  layers: [
    {
      type: "User ID-Token",
      description: "OIDC JWT from identity provider (Google, Keycloak). Consumed during login, not stored by DeepSecure.",
      count: 0,
      active: 0,
      items: [],
    },
    {
      type: "User Session",
      description: "Console/API session for delegating users",
      count: 2,
      active: 2,
      items: [
        {
          id: "usess-001",
          user: "alice@acme.com",
          idp: "google",
          created_at: "2026-06-04T09:00:00Z",
          expires_at: "2026-06-04T17:00:00Z",
          status: "active",
        },
        {
          id: "usess-002",
          user: "bob@acme.com",
          idp: "keycloak",
          created_at: "2026-06-04T10:30:00Z",
          expires_at: "2026-06-04T18:30:00Z",
          status: "active",
        },
      ],
    },
    {
      type: "Delegation",
      description: "User → agent permission grants",
      count: 3,
      active: 2,
      items: [
        {
          id: "del-abc123",
          delegator: "alice@acme.com",
          permissions_count: 24,
          services: ["notion", "slack", "github"],
          created_at: "2026-06-03T00:00:00Z",
          expires_at: "2026-07-03T00:00:00Z",
          status: "active",
        },
        {
          id: "del-def456",
          delegator: "bob@acme.com",
          permissions_count: 12,
          services: ["notion"],
          created_at: "2026-06-01T00:00:00Z",
          expires_at: "2026-07-01T00:00:00Z",
          status: "active",
        },
        {
          id: "del-ghi789",
          delegator: "alice@acme.com",
          permissions_count: 5,
          services: ["notion"],
          created_at: "2026-05-01T00:00:00Z",
          expires_at: "2026-05-17T00:00:00Z",
          status: "expired",
        },
      ],
    },
    {
      type: "Agent Session",
      description: "Authenticated agent sessions with delegated permissions",
      count: 149,
      active: 1,
      items: [
        {
          id: "asess-001",
          session_id: "asess-001abcdef",
          delegator: "alice@acme.com",
          delegation_id: "del-abc123abcdef",
          created_at: "2026-06-04T14:02:28Z",
          expires_at: "2026-06-04T22:02:28Z",
          status: "active",
        },
        {
          id: "asess-002",
          session_id: "asess-002xyz789",
          delegator: "bob@acme.com",
          delegation_id: "del-def456xyz789",
          created_at: "2026-06-04T12:00:00Z",
          expires_at: "2026-06-04T20:00:00Z",
          status: "expired",
        },
      ],
    },
    {
      type: "Task Token",
      description: "Per-task scoped permissions (narrowest scope)",
      count: 0,
      active: 0,
      items: [],
    },
  ],
};

function setupSuccessMock(data: IdentityStackResponse = MOCK_RESPONSE) {
  mockApiClient.mockResolvedValue(data as never);
}

function setupErrorMock() {
  mockApiClient.mockRejectedValue(new Error("Network error"));
}

describe("IdentityStackPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders loading state", () => {
    mockApiClient.mockReturnValue(new Promise(() => {}) as never);
    render(<IdentityStackPanel agentId="agent-1" />);
    expect(screen.getByText(/Loading identity stack/)).toBeInTheDocument();
  });

  it("renders all 5 layer headers", async () => {
    setupSuccessMock();
    render(<IdentityStackPanel agentId="agent-1" />);
    await waitFor(() => {
      expect(screen.getByText("User ID-Token")).toBeInTheDocument();
    });
    expect(screen.getByText("User Session")).toBeInTheDocument();
    expect(screen.getByText("Delegation")).toBeInTheDocument();
    expect(screen.getByText("Agent Session")).toBeInTheDocument();
    expect(screen.getByText("Task Token")).toBeInTheDocument();
  });

  it("accordion expand/collapse — clicking one collapses the other", async () => {
    setupSuccessMock();
    render(<IdentityStackPanel agentId="agent-1" />);
    await waitFor(() => expect(screen.getByText("Delegation")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Delegation"));
    expect(screen.getAllByText("alice@acme.com").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByText("Agent Session"));
    expect(screen.queryByText("Showing 2 of 149")).toBeInTheDocument();
    expect(screen.getByText(/asess-001abc/)).toBeInTheDocument();
  });

  it("User ID-Token shows empty state explanation", async () => {
    setupSuccessMock();
    render(<IdentityStackPanel agentId="agent-1" />);
    await waitFor(() => expect(screen.getByText("User ID-Token")).toBeInTheDocument());

    fireEvent.click(screen.getByText("User ID-Token"));
    expect(
      screen.getByText(/User ID-Tokens are issued by the identity provider/)
    ).toBeInTheDocument();
  });

  it("User Session renders user email, IdP, and status", async () => {
    setupSuccessMock();
    render(<IdentityStackPanel agentId="agent-1" />);
    await waitFor(() => expect(screen.getByText("User Session")).toBeInTheDocument());

    fireEvent.click(screen.getByText("User Session"));
    expect(screen.getByText("alice@acme.com")).toBeInTheDocument();
    expect(screen.getByText("google")).toBeInTheDocument();
    expect(screen.getByText("bob@acme.com")).toBeInTheDocument();
    expect(screen.getByText("keycloak")).toBeInTheDocument();
  });

  it("Delegation renders delegator, permissions count, service badges, and status", async () => {
    setupSuccessMock();
    render(<IdentityStackPanel agentId="agent-1" />);
    await waitFor(() => expect(screen.getByText("Delegation")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Delegation"));
    expect(screen.getAllByText("alice@acme.com").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("24")).toBeInTheDocument();
    expect(screen.getAllByText("Notion").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Slack")).toBeInTheDocument();
    expect(screen.getByText("GitHub")).toBeInTheDocument();
  });

  it("Agent Session renders session ID (monospace truncated), delegator, and status", async () => {
    setupSuccessMock();
    render(<IdentityStackPanel agentId="agent-1" />);
    await waitFor(() => expect(screen.getByText("Agent Session")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Agent Session"));
    expect(screen.getByText(/asess-001abc/)).toBeInTheDocument();
    expect(screen.getByText("alice@acme.com")).toBeInTheDocument();
  });

  it("Task Token shows empty state message", async () => {
    setupSuccessMock();
    render(<IdentityStackPanel agentId="agent-1" />);
    await waitFor(() => expect(screen.getByText("Task Token")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Task Token"));
    expect(
      screen.getByText(/No task tokens.*not yet in production use/)
    ).toBeInTheDocument();
  });

  it("pagination indicator shows for Agent Session", async () => {
    setupSuccessMock();
    render(<IdentityStackPanel agentId="agent-1" />);
    await waitFor(() => expect(screen.getByText("Agent Session")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Agent Session"));
    expect(screen.getByText("Showing 2 of 149")).toBeInTheDocument();
  });

  it("error state shows error message and retry button", async () => {
    setupErrorMock();
    render(<IdentityStackPanel agentId="agent-1" />);
    await waitFor(() => expect(screen.getByText("Network error")).toBeInTheDocument());
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it("badge colors match layer types", async () => {
    setupSuccessMock();
    render(<IdentityStackPanel agentId="agent-1" />);
    await waitFor(() => expect(screen.getByText("User ID-Token")).toBeInTheDocument());

    const idTokenBadge = screen.getByText("User ID-Token");
    expect(idTokenBadge.className).toContain("bg-gray-100");

    const userSessionBadge = screen.getByText("User Session");
    expect(userSessionBadge.className).toContain("bg-amber-100");

    const delegationBadge = screen.getByText("Delegation");
    expect(delegationBadge.className).toContain("bg-blue-100");

    const agentSessionBadge = screen.getByText("Agent Session");
    expect(agentSessionBadge.className).toContain("bg-green-100");

    const taskTokenBadge = screen.getByText("Task Token");
    expect(taskTokenBadge.className).toContain("bg-purple-100");
  });

  it("no layer numbering (L0, L1, L2, L3, L4, L5) anywhere", async () => {
    setupSuccessMock();
    const { container } = render(<IdentityStackPanel agentId="agent-1" />);
    await waitFor(() => expect(screen.getByText("User ID-Token")).toBeInTheDocument());

    const text = container.textContent ?? "";
    for (const label of ["L0", "L1", "L2", "L3", "L4", "L5"]) {
      expect(text).not.toContain(label);
    }
  });
});
