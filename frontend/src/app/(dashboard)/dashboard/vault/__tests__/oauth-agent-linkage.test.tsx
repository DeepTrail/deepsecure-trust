import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

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

vi.mock("@/hooks/useUserRole", () => ({
  useUserRole: vi.fn(),
}));

vi.mock("@/components/feedback/page-skeleton", () => ({
  PageSkeleton: () => <div data-testid="page-skeleton">Loading...</div>,
}));

vi.mock("@/components/feedback/error-card", () => ({
  ErrorCard: ({ title, message }: { title: string; message: string }) => (
    <div data-testid="error-card">
      <span>{title}</span>
      <span>{message}</span>
    </div>
  ),
}));

vi.mock("@/components/feedback/empty-state", () => ({
  EmptyState: ({ title, description }: { title: string; description?: string }) => (
    <div data-testid="empty-state">
      <span>{title}</span>
      {description && <span>{description}</span>}
    </div>
  ),
}));

import VaultPage from "../page";
import { apiClient } from "@/lib/api/client";
import { useUserRole } from "@/hooks/useUserRole";

const mockApiClient = apiClient as ReturnType<typeof vi.fn>;
const mockUseUserRole = useUserRole as ReturnType<typeof vi.fn>;

function setupRole(isAdmin = false) {
  mockUseUserRole.mockReturnValue({
    role: isAdmin ? "admin" : "employee",
    isAdmin,
    isLoading: false,
    error: null,
  });
}

const notionToken = {
  service_id: "notion",
  token_ref: "vault://test-notion",
  status: "active" as const,
  scopes_granted: ["read_content"],
  created_at: "2026-06-01T10:00:00Z",
  expires_at: "2026-06-10T10:00:00Z",
  last_used_at: null,
  last_refreshed_at: null,
  refresh_count: 0,
  refresh_log: [],
};

const slackToken = {
  ...notionToken,
  service_id: "slack",
  token_ref: "vault://test-slack",
  scopes_granted: ["channels:read"],
};

const githubToken = {
  ...notionToken,
  service_id: "github",
  token_ref: "vault://test-github",
  scopes_granted: ["repos"],
};

function mockEndpoints(overrides: Record<string, unknown> = {}) {
  mockApiClient.mockImplementation((url: string) => {
    if (url === "vault/encryption-status") {
      return Promise.resolve({ service_credentials: "fernet", vault_tokens: "fernet", secrets: "shamir_split_key" });
    }
    if (url === "vault/user-tokens") {
      return Promise.resolve(overrides["vault/user-tokens"] ?? { tokens: [notionToken, slackToken, githubToken] });
    }
    if (url === "vault/user-tokens/agent-linkage") {
      return Promise.resolve(overrides["vault/user-tokens/agent-linkage"] ?? { linkage: {} });
    }
    if (url === "vault/secrets") {
      return Promise.resolve({ secrets: [] });
    }
    if (url === "vault/user-credentials") {
      return Promise.resolve({ credentials: [] });
    }
    if (url === "vault/agent-sessions") {
      return Promise.resolve({ sessions: [], total: 0 });
    }
    if (url === "admin/services") {
      return Promise.resolve([]);
    }
    return Promise.resolve({});
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("OAuth Agent Linkage — Phase 4", () => {
  it('shows "Used by" column header', async () => {
    setupRole(false);
    mockEndpoints();
    render(<VaultPage />);

    fireEvent.click(await screen.findByText("OAuth Tokens"));

    await waitFor(() => {
      expect(screen.getByText("Used by")).toBeInTheDocument();
    });
  });

  it("shows agent badge for linked service", async () => {
    setupRole(false);
    mockEndpoints({
      "vault/user-tokens/agent-linkage": {
        linkage: {
          notion: [{ agent_id: "agent-a", agent_name: "Debugging Agent" }],
          slack: [],
          github: [],
        },
      },
    });

    render(<VaultPage />);
    fireEvent.click(await screen.findByText("OAuth Tokens"));

    await waitFor(() => {
      expect(screen.getByText("Debugging Agent")).toBeInTheDocument();
    });
  });

  it("shows multiple agent badges", async () => {
    setupRole(false);
    mockEndpoints({
      "vault/user-tokens/agent-linkage": {
        linkage: {
          notion: [
            { agent_id: "agent-a", agent_name: "Debugging Agent" },
            { agent_id: "agent-b", agent_name: "Thunderbolt Agent" },
          ],
          slack: [],
          github: [],
        },
      },
    });

    render(<VaultPage />);
    fireEvent.click(await screen.findByText("OAuth Tokens"));

    await waitFor(() => {
      expect(screen.getByText("Debugging Agent")).toBeInTheDocument();
      expect(screen.getByText("Thunderbolt Agent")).toBeInTheDocument();
    });
  });

  it("shows overflow badge when >2 agents", async () => {
    setupRole(false);
    mockEndpoints({
      "vault/user-tokens/agent-linkage": {
        linkage: {
          notion: [
            { agent_id: "a1", agent_name: "Agent Alpha" },
            { agent_id: "a2", agent_name: "Agent Beta" },
            { agent_id: "a3", agent_name: "Agent Gamma" },
          ],
          slack: [],
          github: [],
        },
      },
    });

    render(<VaultPage />);
    fireEvent.click(await screen.findByText("OAuth Tokens"));

    await waitFor(() => {
      expect(screen.getByText("Agent Alpha")).toBeInTheDocument();
      expect(screen.getByText("Agent Beta")).toBeInTheDocument();
      expect(screen.getByText("+1")).toBeInTheDocument();
    });
    expect(screen.queryByText("Agent Gamma")).not.toBeInTheDocument();
  });

  it("shows em-dash when no agents linked", async () => {
    setupRole(false);
    mockEndpoints({
      "vault/user-tokens/agent-linkage": {
        linkage: { notion: [], slack: [], github: [] },
      },
    });

    render(<VaultPage />);
    fireEvent.click(await screen.findByText("OAuth Tokens"));

    await waitFor(() => {
      const dashes = screen.getAllByText("—");
      expect(dashes.length).toBeGreaterThanOrEqual(3);
    });
  });

  it("handles empty linkage gracefully", async () => {
    setupRole(false);
    mockEndpoints({
      "vault/user-tokens/agent-linkage": { linkage: {} },
    });

    render(<VaultPage />);
    fireEvent.click(await screen.findByText("OAuth Tokens"));

    await waitFor(() => {
      expect(screen.getByText("notion")).toBeInTheDocument();
    });
  });

  it("handles linkage API failure gracefully", async () => {
    setupRole(false);
    mockApiClient.mockImplementation((url: string) => {
      if (url === "vault/encryption-status") {
        return Promise.resolve({ service_credentials: "fernet", vault_tokens: "fernet", secrets: "shamir_split_key" });
      }
      if (url === "vault/user-tokens") {
        return Promise.resolve({ tokens: [notionToken] });
      }
      if (url === "vault/user-tokens/agent-linkage") {
        return Promise.reject(new Error("Network error"));
      }
      return Promise.resolve({});
    });

    render(<VaultPage />);
    fireEvent.click(await screen.findByText("OAuth Tokens"));

    await waitFor(() => {
      expect(screen.getByText("notion")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("error-card")).not.toBeInTheDocument();
  });

  it("calls both endpoints in parallel", async () => {
    setupRole(false);
    mockEndpoints();
    render(<VaultPage />);

    fireEvent.click(await screen.findByText("OAuth Tokens"));

    await waitFor(() => {
      expect(screen.getByText("notion")).toBeInTheDocument();
    });

    expect(mockApiClient).toHaveBeenCalledWith("vault/user-tokens");
    expect(mockApiClient).toHaveBeenCalledWith("vault/user-tokens/agent-linkage");
  });
});
