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

  it("toggles the create form when Register Agent is clicked", async () => {
    mockApiClient.mockResolvedValueOnce(AGENTS);
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByText("Alpha Agent")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /register agent/i }));
    expect(screen.getByLabelText("Agent ID")).toBeInTheDocument();
    expect(screen.getByLabelText("Name")).toBeInTheDocument();
    expect(screen.getByLabelText(/public key/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /register agent/i }));
    expect(screen.queryByLabelText("Agent ID")).not.toBeInTheDocument();
  });

  it("shows Register Agent button in empty state that opens the form", async () => {
    mockApiClient
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([]);
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /register agent/i }));

    await waitFor(() => {
      expect(screen.getByLabelText("Agent ID")).toBeInTheDocument();
    });
  });

  it("submits create form with correct payload", async () => {
    mockApiClient.mockResolvedValueOnce(AGENTS);
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByText("Alpha Agent")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /register agent/i }));

    fireEvent.change(screen.getByLabelText("Agent ID"), {
      target: { value: "new-agent" },
    });
    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "New Agent" },
    });
    fireEvent.change(screen.getByLabelText(/public key/i), {
      target: { value: "c29tZWtleQ==" },
    });

    mockApiClient
      .mockResolvedValueOnce(undefined)
      .mockResolvedValueOnce(AGENTS);

    fireEvent.click(screen.getByRole("button", { name: /^create$/i }));

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith("agents/", {
        method: "POST",
        body: JSON.stringify({
          agent_id: "new-agent",
          name: "New Agent",
          public_key: "c29tZWtleQ==",
        }),
      });
    });
  });

  it("uses agent_id as name when name field is empty", async () => {
    mockApiClient.mockResolvedValueOnce(AGENTS);
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByText("Alpha Agent")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /register agent/i }));

    fireEvent.change(screen.getByLabelText("Agent ID"), {
      target: { value: "my-agent" },
    });

    mockApiClient
      .mockResolvedValueOnce(undefined)
      .mockResolvedValueOnce(AGENTS);

    fireEvent.click(screen.getByRole("button", { name: /^create$/i }));

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith("agents/", {
        method: "POST",
        body: JSON.stringify({
          agent_id: "my-agent",
          name: "my-agent",
        }),
      });
    });
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

  it("shows 409 conflict error message in create form", async () => {
    mockApiClient.mockResolvedValueOnce(AGENTS);
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByText("Alpha Agent")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /register agent/i }));
    fireEvent.change(screen.getByLabelText("Agent ID"), {
      target: { value: "existing-agent" },
    });

    mockApiClient.mockRejectedValueOnce(
      new ApiError(409, "Conflict")
    );

    fireEvent.click(screen.getByRole("button", { name: /^create$/i }));

    await waitFor(() => {
      expect(
        screen.getByText("An agent with this ID already exists.")
      ).toBeInTheDocument();
    });
  });

  it("shows generic create error for non-409 failures", async () => {
    mockApiClient.mockResolvedValueOnce(AGENTS);
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByText("Alpha Agent")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /register agent/i }));
    fireEvent.change(screen.getByLabelText("Agent ID"), {
      target: { value: "fail-agent" },
    });

    mockApiClient.mockRejectedValueOnce(new Error("Network error"));

    fireEvent.click(screen.getByRole("button", { name: /^create$/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Failed to create agent. Please try again.")
      ).toBeInTheDocument();
    });
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

  it("cancel button in create form hides the form", async () => {
    mockApiClient.mockResolvedValueOnce(AGENTS);
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByText("Alpha Agent")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /register agent/i }));
    expect(screen.getByLabelText("Agent ID")).toBeInTheDocument();

    mockApiClient.mockResolvedValueOnce(AGENTS);
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));

    await waitFor(() => {
      expect(screen.queryByLabelText("Agent ID")).not.toBeInTheDocument();
    });
  });
});
