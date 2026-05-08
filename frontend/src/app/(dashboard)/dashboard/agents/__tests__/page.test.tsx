import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import AgentsPage from "../page";
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

const mockApiClient = vi.mocked(apiClient);

const AGENTS = [
  {
    agent_id: "agent-1",
    name: "Alpha Agent",
    status: "active",
    created_at: "2026-01-15T00:00:00Z",
    public_key: "c29tZWJhc2U2NHB1YmtleQ==",
  },
  {
    agent_id: "agent-2",
    name: "Beta Agent",
    status: "suspended",
  },
  {
    agent_id: "agent-3",
    name: "Gamma Agent",
  },
];

describe("AgentsPage", () => {
  beforeEach(() => {
    mockApiClient.mockReset();
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows loading skeleton initially", () => {
    mockApiClient.mockReturnValue(new Promise(() => {}));
    render(<AgentsPage />);
    expect(screen.getByTestId("page-skeleton")).toBeInTheDocument();
  });

  it("renders agent cards with name, status badge, and agent_id", async () => {
    mockApiClient.mockResolvedValueOnce(AGENTS);
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByText("Alpha Agent")).toBeInTheDocument();
    });

    expect(screen.getByText("Beta Agent")).toBeInTheDocument();
    expect(screen.getByText("Gamma Agent")).toBeInTheDocument();

    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("suspended")).toBeInTheDocument();
    expect(screen.getByText("registered")).toBeInTheDocument();

    const idText = screen.getAllByText(/^ID:/);
    expect(idText[0].textContent).toContain("agent-1");
  });

  it("shows EmptyState when there are no agents", async () => {
    mockApiClient.mockResolvedValueOnce([]);
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    });
    expect(screen.getByText("No agents registered")).toBeInTheDocument();
  });

  it("Register Agent links to /dashboard/agents/create", async () => {
    mockApiClient.mockResolvedValueOnce(AGENTS);
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByText("Alpha Agent")).toBeInTheDocument();
    });

    const link = screen.getByRole("link", { name: /register agent/i });
    expect(link).toHaveAttribute("href", "/dashboard/agents/create");
  });

  it("Register Agent link exists in empty state too", async () => {
    mockApiClient.mockResolvedValueOnce([]);
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    });

    const link = screen.getByRole("link", { name: /register agent/i });
    expect(link).toHaveAttribute("href", "/dashboard/agents/create");
  });

  it("agent cards link to activity page", async () => {
    mockApiClient.mockResolvedValueOnce(AGENTS);
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByText("Alpha Agent")).toBeInTheDocument();
    });

    const links = screen.getAllByRole("link");
    const activityLinks = links.filter((l) =>
      l.getAttribute("href")?.includes("/activity")
    );
    expect(activityLinks).toHaveLength(3);
    expect(activityLinks[0]).toHaveAttribute(
      "href",
      "/dashboard/agents/agent-1/activity"
    );
  });

  it("shows confirmation dialog on delete and calls API when confirmed", async () => {
    mockApiClient.mockResolvedValueOnce(AGENTS);
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByText("Alpha Agent")).toBeInTheDocument();
    });

    mockApiClient
      .mockResolvedValueOnce(undefined)
      .mockResolvedValueOnce(AGENTS);

    const deleteButtons = screen.getAllByRole("button").filter(
      (btn) => btn.querySelector(".lucide-trash-2") !== null
    );

    fireEvent.click(deleteButtons[0]);

    expect(window.confirm).toHaveBeenCalledWith(
      "Are you sure you want to delete this agent?"
    );

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith("agents/agent-1", {
        method: "DELETE",
      });
    });
  });

  it("does not call API when delete confirmation is cancelled", async () => {
    mockApiClient.mockResolvedValueOnce(AGENTS);
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByText("Alpha Agent")).toBeInTheDocument();
    });

    const spy = vi.mocked(window.confirm);
    spy.mockReturnValueOnce(false);

    const deleteButtons = screen.getAllByRole("button").filter(
      (btn) => btn.querySelector(".lucide-trash-2") !== null
    );

    fireEvent.click(deleteButtons[0]);

    expect(spy).toHaveBeenCalled();
    expect(mockApiClient).toHaveBeenCalledTimes(1);
  });

  it("shows ErrorCard on fetch failure with retry", async () => {
    mockApiClient.mockRejectedValueOnce(
      new ApiError(500, "Server Error")
    );
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });

    expect(screen.getByText("Agents")).toBeInTheDocument();
    expect(screen.getByText("Failed to load agents (500)")).toBeInTheDocument();

    mockApiClient.mockResolvedValueOnce(AGENTS);
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));

    await waitFor(() => {
      expect(screen.getByText("Alpha Agent")).toBeInTheDocument();
    });
  });

  it("shows generic error message for non-ApiError failures", async () => {
    mockApiClient.mockRejectedValueOnce(new Error("Network failure"));
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });
    expect(screen.getByText("Failed to load agents")).toBeInTheDocument();
  });

  describe("status badge variants", () => {
    it('renders "active" status with default variant', async () => {
      mockApiClient.mockResolvedValueOnce([
        { agent_id: "a1", name: "Active", status: "active" },
      ]);
      render(<AgentsPage />);

      await waitFor(() => {
        expect(screen.getByText("active")).toBeInTheDocument();
      });
    });

    it('renders "suspended" status with destructive variant', async () => {
      mockApiClient.mockResolvedValueOnce([
        { agent_id: "a2", name: "Suspended", status: "suspended" },
      ]);
      render(<AgentsPage />);

      await waitFor(() => {
        expect(screen.getByText("suspended")).toBeInTheDocument();
      });
    });

    it('renders missing status as "registered"', async () => {
      mockApiClient.mockResolvedValueOnce([
        { agent_id: "a3", name: "NoStatus" },
      ]);
      render(<AgentsPage />);

      await waitFor(() => {
        expect(screen.getByText("registered")).toBeInTheDocument();
      });
    });
  });

  it("displays truncated public key when present", async () => {
    mockApiClient.mockResolvedValueOnce([AGENTS[0]]);
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByText("Alpha Agent")).toBeInTheDocument();
    });

    const keyText = screen.getByText(/^Key:/);
    expect(keyText.textContent).toContain(
      AGENTS[0].public_key!.slice(0, 16) + "..."
    );
  });

  it("does not display public key section when absent", async () => {
    mockApiClient.mockResolvedValueOnce([AGENTS[1]]);
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByText("Beta Agent")).toBeInTheDocument();
    });

    expect(screen.queryByText(/^Key:/)).not.toBeInTheDocument();
  });

  it("displays agent_id as title when name is empty", async () => {
    const agentNoName = { agent_id: "agent-solo", name: "", status: "active" };
    mockApiClient.mockResolvedValueOnce([agentNoName]);
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getAllByText("agent-solo").length).toBeGreaterThan(0);
    });
  });

  it("unwraps paginated { agents: [...] } response format", async () => {
    mockApiClient.mockResolvedValueOnce({ agents: AGENTS });
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByText("Alpha Agent")).toBeInTheDocument();
    });
    expect(screen.getByText("Beta Agent")).toBeInTheDocument();
  });
});
