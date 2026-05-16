import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import DelegationPage from "../page";
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

vi.mock("@/components/feedback/empty-state", () => ({
  EmptyState: ({
    title,
    description,
  }: {
    title: string;
    description?: string;
    icon?: React.ReactNode;
  }) => (
    <div data-testid="empty-state">
      <span>{title}</span>
      {description && <span>{description}</span>}
    </div>
  ),
}));

const mockApiClient = vi.mocked(apiClient);

const AGENTS = [
  { agent_id: "agent-1", name: "Alpha Agent" },
  { agent_id: "agent-2", name: "Beta Agent" },
];

const DELEGATIONS = [
  {
    delegation_id: "del-001",
    agent_id: "agent-1",
    permissions: ["notion:pages:read", "slack:messages:write"],
    expires_in: 3600,
    created_at: "2026-05-06T10:00:00Z",
  },
  {
    delegation_id: "del-002",
    agent_id: "agent-2",
    permissions: ["github:repos:read"],
    expires_in: 86400,
    created_at: null,
  },
];

describe("DelegationPage", () => {
  beforeEach(() => {
    mockApiClient.mockReset();
  });

  it("shows loading skeleton initially", () => {
    mockApiClient.mockReturnValue(new Promise(() => {}));
    render(<DelegationPage />);
    expect(screen.getByTestId("page-skeleton")).toBeInTheDocument();
  });

  it("renders delegation cards when data loads", async () => {
    mockApiClient
      .mockResolvedValueOnce(DELEGATIONS)
      .mockResolvedValueOnce(AGENTS);

    render(<DelegationPage />);

    await waitFor(() => {
      expect(screen.getByText("Alpha Agent")).toBeInTheDocument();
    });

    expect(screen.getByText("del-001")).toBeInTheDocument();
    expect(screen.getByText("del-002")).toBeInTheDocument();
  });

  it("shows page title when loaded", async () => {
    mockApiClient
      .mockResolvedValueOnce(DELEGATIONS)
      .mockResolvedValueOnce(AGENTS);

    render(<DelegationPage />);

    await waitFor(() => {
      expect(screen.getByText("Delegation")).toBeInTheDocument();
    });
  });

  it("shows empty state when no delegations exist", async () => {
    mockApiClient
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce(AGENTS);

    render(<DelegationPage />);

    await waitFor(() => {
      expect(screen.getByText("No delegations yet")).toBeInTheDocument();
    });
  });

  it("shows ErrorCard on API failure", async () => {
    mockApiClient.mockImplementation(() => {
      throw new ApiError(500, "Server Error");
    });

    render(<DelegationPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });
    expect(
      screen.getByText("Failed to load delegations (500)"),
    ).toBeInTheDocument();

    mockApiClient.mockReset();
  });

  it("shows generic error for non-ApiError failures", async () => {
    mockApiClient.mockImplementation(() => {
      throw new Error("Network failure");
    });

    render(<DelegationPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });
    expect(
      screen.getByText("Failed to load delegations"),
    ).toBeInTheDocument();

    mockApiClient.mockReset();
  });

  it("handles agents in object format with .agents property", async () => {
    mockApiClient
      .mockResolvedValueOnce(DELEGATIONS)
      .mockResolvedValueOnce({ agents: AGENTS });

    render(<DelegationPage />);

    await waitFor(() => {
      expect(screen.getByText("Alpha Agent")).toBeInTheDocument();
    });
  });

  it("renders permission counts per delegation", async () => {
    mockApiClient
      .mockResolvedValueOnce(DELEGATIONS)
      .mockResolvedValueOnce(AGENTS);

    render(<DelegationPage />);

    await waitFor(() => {
      expect(screen.getByText("2 permissions")).toBeInTheDocument();
    });
    expect(screen.getByText("1 permission")).toBeInTheDocument();
  });

  it("retries data fetch when retry button is clicked", async () => {
    mockApiClient.mockImplementation(() => {
      throw new ApiError(500, "Server Error");
    });

    render(<DelegationPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });

    mockApiClient.mockReset();
    mockApiClient
      .mockResolvedValueOnce(DELEGATIONS)
      .mockResolvedValueOnce(AGENTS);

    const retryBtn = screen.getByRole("button", { name: /retry/i });
    retryBtn.click();

    await waitFor(() => {
      expect(screen.getByText("Alpha Agent")).toBeInTheDocument();
    });
  });

  it("renders Create Delegation link", async () => {
    mockApiClient
      .mockResolvedValueOnce(DELEGATIONS)
      .mockResolvedValueOnce(AGENTS);

    render(<DelegationPage />);

    await waitFor(() => {
      expect(screen.getByText("Alpha Agent")).toBeInTheDocument();
    });

    const link = screen.getByRole("link", { name: /create delegation/i });
    expect(link).toHaveAttribute("href", "/dashboard/delegation/create");
  });

  it("handles delegations with missing permissions gracefully", async () => {
    mockApiClient
      .mockResolvedValueOnce([
        {
          delegation_id: "del-no-perms",
          agent_id: "agent-1",
          expires_in: 3600,
          created_at: null,
        },
      ])
      .mockResolvedValueOnce(AGENTS);

    render(<DelegationPage />);

    await waitFor(() => {
      expect(screen.getByText("del-no-perms")).toBeInTheDocument();
    });
  });
});
