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

function mockEndpoints(overrides: Record<string, unknown> = {}) {
  mockApiClient.mockImplementation((url: string) => {
    if (url === "vault/encryption-status") {
      return Promise.resolve(overrides["vault/encryption-status"] ?? {
        service_credentials: "fernet",
        vault_tokens: "fernet",
        secrets: "shamir_split_key",
      });
    }
    if (url === "vault/user-tokens") {
      return Promise.resolve(overrides["vault/user-tokens"] ?? { tokens: [] });
    }
    if (url === "vault/secrets") {
      return Promise.resolve(overrides["vault/secrets"] ?? { secrets: [] });
    }
    if (url === "vault/user-credentials") {
      return Promise.resolve(overrides["vault/user-credentials"] ?? { credentials: [] });
    }
    if (url === "vault/agent-sessions") {
      return Promise.resolve(overrides["vault/agent-sessions"] ?? { sessions: [], total: 0 });
    }
    if (url === "admin/services") {
      return Promise.resolve(overrides["admin/services"] ?? []);
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

describe("Vault tabs — Phase 3", () => {
  it('shows "Split-Key Credentials" tab instead of "Agent Credentials"', async () => {
    setupRole(false);
    mockEndpoints();
    render(<VaultPage />);

    await waitFor(() => {
      expect(screen.getByText("Split-Key Credentials")).toBeInTheDocument();
    });
    expect(screen.queryByText("Agent Credentials")).not.toBeInTheDocument();
  });

  it('shows "Agent Sessions" tab', async () => {
    setupRole(false);
    mockEndpoints();
    render(<VaultPage />);

    await waitFor(() => {
      expect(screen.getByText("Agent Sessions")).toBeInTheDocument();
    });
  });

  it("admin sees all five tabs including Service Credentials", async () => {
    setupRole(true);
    mockEndpoints();
    render(<VaultPage />);

    await waitFor(() => {
      expect(screen.getByText("Service Credentials")).toBeInTheDocument();
    });
    expect(screen.getByText("OAuth Tokens")).toBeInTheDocument();
    expect(screen.getByText("Secrets")).toBeInTheDocument();
    expect(screen.getByText("Split-Key Credentials")).toBeInTheDocument();
    expect(screen.getByText("Agent Sessions")).toBeInTheDocument();
  });

  it("Split-Key Credentials tab shows subtitle", async () => {
    setupRole(false);
    mockEndpoints();
    render(<VaultPage />);

    await waitFor(() => {
      expect(screen.getByText("Split-Key Credentials")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Split-Key Credentials"));

    await waitFor(() => {
      expect(screen.getByText(/Ed25519 agents only/)).toBeInTheDocument();
    });
  });

  it("Split-Key Credentials tab shows updated empty state", async () => {
    setupRole(false);
    mockEndpoints();
    render(<VaultPage />);

    await waitFor(() => {
      expect(screen.getByText("Split-Key Credentials")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Split-Key Credentials"));

    await waitFor(() => {
      expect(screen.getByText("No split-key credentials")).toBeInTheDocument();
    });
  });

  it("Agent Sessions tab shows empty state when no sessions", async () => {
    setupRole(false);
    mockEndpoints();
    render(<VaultPage />);

    await waitFor(() => {
      expect(screen.getByText("Agent Sessions")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Agent Sessions"));

    await waitFor(() => {
      expect(screen.getByText("No agent sessions")).toBeInTheDocument();
    });
  });

  it("Agent Sessions tab shows session data", async () => {
    setupRole(false);
    mockEndpoints({
      "vault/agent-sessions": {
        sessions: [
          {
            session_id: 1,
            agent_id: "debugging-agent",
            agent_name: "Debugging Agent",
            delegation_id: 10,
            permissions_count: 3,
            status: "active",
            created_at: "2026-06-01T10:00:00Z",
            expires_at: "2026-06-01T18:00:00Z",
            last_activity_at: "2026-06-01T12:30:00Z",
          },
        ],
        total: 1,
      },
    });

    render(<VaultPage />);

    await waitFor(() => {
      expect(screen.getByText("Agent Sessions")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Agent Sessions"));

    await waitFor(() => {
      expect(screen.getByText("Debugging Agent")).toBeInTheDocument();
    });
    expect(screen.getByText("debugging-agent")).toBeInTheDocument();
    expect(screen.getByText("3 scopes")).toBeInTheDocument();
  });

  it("Agent Sessions tab shows View in Fleet link", async () => {
    setupRole(false);
    mockEndpoints({
      "vault/agent-sessions": {
        sessions: [
          {
            session_id: 1,
            agent_id: "test-agent",
            agent_name: "Test",
            delegation_id: 1,
            permissions_count: 1,
            status: "active",
            created_at: "2026-06-01T10:00:00Z",
            expires_at: "2026-06-01T18:00:00Z",
            last_activity_at: null,
          },
        ],
        total: 1,
      },
    });

    render(<VaultPage />);

    await waitFor(() => {
      expect(screen.getByText("Agent Sessions")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Agent Sessions"));

    await waitFor(() => {
      expect(screen.getByText("View in Fleet")).toBeInTheDocument();
    });
    const link = screen.getByText("View in Fleet").closest("a");
    expect(link).toHaveAttribute("href", "/dashboard/admin/agents");
  });

  it("Agent Sessions tab shows pagination text when total exceeds displayed", async () => {
    const sessions = Array.from({ length: 5 }, (_, i) => ({
      session_id: i + 1,
      agent_id: `agent-${i}`,
      agent_name: `Agent ${i}`,
      delegation_id: i,
      permissions_count: 1,
      status: "active" as const,
      created_at: "2026-06-01T10:00:00Z",
      expires_at: "2026-06-01T18:00:00Z",
      last_activity_at: "2026-06-01T12:00:00Z",
    }));

    setupRole(false);
    mockEndpoints({
      "vault/agent-sessions": { sessions, total: 20 },
    });

    render(<VaultPage />);

    await waitFor(() => {
      expect(screen.getByText("Agent Sessions")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Agent Sessions"));

    await waitFor(() => {
      expect(screen.getByText("Showing 5 of 20 sessions")).toBeInTheDocument();
    });
  });

  it("Agent Sessions tab shows singular scope text for 1 permission", async () => {
    setupRole(false);
    mockEndpoints({
      "vault/agent-sessions": {
        sessions: [
          {
            session_id: 1,
            agent_id: "single-perm",
            agent_name: "Single Perm Agent",
            delegation_id: 1,
            permissions_count: 1,
            status: "active",
            created_at: "2026-06-01T10:00:00Z",
            expires_at: "2026-06-01T18:00:00Z",
            last_activity_at: null,
          },
        ],
        total: 1,
      },
    });

    render(<VaultPage />);

    await waitFor(() => {
      expect(screen.getByText("Agent Sessions")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Agent Sessions"));

    await waitFor(() => {
      expect(screen.getByText("1 scope")).toBeInTheDocument();
    });
  });
});
