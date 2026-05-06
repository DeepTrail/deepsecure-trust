import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

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

import TasksPage from "../page";
import { apiClient, ApiError } from "@/lib/api/client";

const mockApiClient = apiClient as ReturnType<typeof vi.fn>;

const pendingTask = {
  task_id: "task-001",
  name: "Process invoices",
  description: "Process all pending invoices for Q1",
  status: "pending",
  agent_id: "agent-alpha",
  created_at: "2026-04-01T09:00:00Z",
};

const activeTask = {
  task_id: "task-002",
  name: "Sync contacts",
  status: "active",
  agent_id: "agent-beta",
};

const completedTask = {
  task_id: "task-003",
  name: "Generate report",
  status: "completed",
};

const revokedTask = {
  task_id: "task-004",
  name: "Old migration",
  status: "revoked",
};

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("TasksPage", () => {
  it("shows loading skeleton initially", () => {
    mockApiClient.mockReturnValue(new Promise(() => {}));
    render(<TasksPage />);
    expect(screen.getByTestId("page-skeleton")).toBeInTheDocument();
  });

  it("renders task cards with name, status badge, and description", async () => {
    mockApiClient.mockResolvedValueOnce([pendingTask, activeTask]);
    render(<TasksPage />);

    await waitFor(() => {
      expect(screen.getByText("Process invoices")).toBeInTheDocument();
    });

    expect(screen.getByText("Sync contacts")).toBeInTheDocument();
    expect(
      screen.getByText("Process all pending invoices for Q1")
    ).toBeInTheDocument();
    expect(screen.getByText("pending")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
  });

  it("shows EmptyState when no tasks", async () => {
    mockApiClient.mockResolvedValueOnce([]);
    render(<TasksPage />);

    await waitFor(() => {
      expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    });
    expect(screen.getByText("No tasks")).toBeInTheDocument();
  });

  it("Create Task button toggles the create form", async () => {
    mockApiClient.mockResolvedValueOnce([]);
    render(<TasksPage />);

    await waitFor(() => {
      expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Create Task/i }));

    await waitFor(() => {
      expect(screen.getByLabelText("Task Name")).toBeInTheDocument();
    });
    expect(screen.getByLabelText("Agent ID")).toBeInTheDocument();
    expect(screen.getByLabelText("Description")).toBeInTheDocument();
  });

  it("create form has name, description, and agent_id (required) fields", async () => {
    mockApiClient.mockResolvedValueOnce([pendingTask]);
    render(<TasksPage />);

    await waitFor(() => {
      expect(screen.getByText("Process invoices")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Create Task/i }));

    await waitFor(() => {
      expect(screen.getByLabelText("Task Name")).toBeInTheDocument();
    });

    const nameInput = screen.getByLabelText("Task Name");
    const agentInput = screen.getByLabelText("Agent ID");
    const descInput = screen.getByLabelText("Description");

    expect(nameInput).toHaveAttribute("required");
    expect(agentInput).toHaveAttribute("required");
    expect(descInput).not.toHaveAttribute("required");
  });

  it("submitting create form calls apiClient POST", async () => {
    mockApiClient
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce(undefined)
      .mockResolvedValueOnce([{ task_id: "new-1", name: "New Task", status: "pending" }]);

    render(<TasksPage />);

    await waitFor(() => {
      expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Create Task/i }));

    await waitFor(() => {
      expect(screen.getByLabelText("Task Name")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("Task Name"), {
      target: { value: "New Task" },
    });
    fireEvent.change(screen.getByLabelText("Agent ID"), {
      target: { value: "agent-gamma" },
    });
    fireEvent.change(screen.getByLabelText("Description"), {
      target: { value: "Do something" },
    });

    fireEvent.click(screen.getByRole("button", { name: /^Create$/i }));

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith("tasks/", {
        method: "POST",
        body: JSON.stringify({
          name: "New Task",
          description: "Do something",
          agent_id: "agent-gamma",
        }),
      });
    });
  });

  it("pending task shows Activate and Revoke buttons", async () => {
    mockApiClient.mockResolvedValueOnce([pendingTask]);
    render(<TasksPage />);

    await waitFor(() => {
      expect(screen.getByText("Process invoices")).toBeInTheDocument();
    });

    expect(
      screen.getByRole("button", { name: /Activate/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Revoke/i })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Complete/i })
    ).not.toBeInTheDocument();
  });

  it("active task shows Complete and Revoke buttons", async () => {
    mockApiClient.mockResolvedValueOnce([activeTask]);
    render(<TasksPage />);

    await waitFor(() => {
      expect(screen.getByText("Sync contacts")).toBeInTheDocument();
    });

    expect(
      screen.getByRole("button", { name: /Complete/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Revoke/i })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Activate/i })
    ).not.toBeInTheDocument();
  });

  it("revoke button shows confirmation dialog", async () => {
    const confirmSpy = vi
      .spyOn(window, "confirm")
      .mockReturnValue(false);

    mockApiClient.mockResolvedValueOnce([pendingTask]);
    render(<TasksPage />);

    await waitFor(() => {
      expect(screen.getByText("Process invoices")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Revoke/i }));

    expect(confirmSpy).toHaveBeenCalledWith("Revoke this task?");
  });

  it("cancelling revoke does not call API", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);

    mockApiClient.mockResolvedValueOnce([pendingTask]);
    render(<TasksPage />);

    await waitFor(() => {
      expect(screen.getByText("Process invoices")).toBeInTheDocument();
    });

    const callCountBefore = mockApiClient.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: /Revoke/i }));

    expect(mockApiClient).toHaveBeenCalledTimes(callCountBefore);
  });

  it("activate action calls correct API endpoint", async () => {
    mockApiClient
      .mockResolvedValueOnce([pendingTask])
      .mockResolvedValueOnce(undefined)
      .mockResolvedValueOnce([{ ...pendingTask, status: "active" }]);

    render(<TasksPage />);

    await waitFor(() => {
      expect(screen.getByText("Process invoices")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Activate/i }));

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith("tasks/task-001/activate", {
        method: "POST",
      });
    });
  });

  it("complete action calls correct API endpoint", async () => {
    mockApiClient
      .mockResolvedValueOnce([activeTask])
      .mockResolvedValueOnce(undefined)
      .mockResolvedValueOnce([{ ...activeTask, status: "completed" }]);

    render(<TasksPage />);

    await waitFor(() => {
      expect(screen.getByText("Sync contacts")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Complete/i }));

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith("tasks/task-002/complete", {
        method: "POST",
      });
    });
  });

  it("revoke action calls correct API endpoint when confirmed", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);

    mockApiClient
      .mockResolvedValueOnce([activeTask])
      .mockResolvedValueOnce(undefined)
      .mockResolvedValueOnce([{ ...activeTask, status: "revoked" }]);

    render(<TasksPage />);

    await waitFor(() => {
      expect(screen.getByText("Sync contacts")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Revoke/i }));

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith("tasks/task-002/revoke", {
        method: "POST",
      });
    });
  });

  it("shows ErrorCard on fetch failure with retry", async () => {
    const { ApiError: MockApiError } = await import("@/lib/api/client");
    mockApiClient.mockRejectedValueOnce(
      new MockApiError(502, "Bad Gateway")
    );

    render(<TasksPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });
    expect(
      screen.getByText("Failed to load tasks (502)")
    ).toBeInTheDocument();

    mockApiClient.mockResolvedValueOnce([pendingTask]);
    fireEvent.click(screen.getByRole("button", { name: /Retry/i }));

    await waitFor(() => {
      expect(screen.getByText("Process invoices")).toBeInTheDocument();
    });
  });

  it("status badge variants: pending=secondary, active=default, completed=outline, revoked=destructive", async () => {
    mockApiClient.mockResolvedValueOnce([
      pendingTask,
      activeTask,
      completedTask,
      revokedTask,
    ]);

    render(<TasksPage />);

    await waitFor(() => {
      expect(screen.getByText("Process invoices")).toBeInTheDocument();
    });

    const badges = screen.getAllByText(
      /^(pending|active|completed|revoked)$/
    );
    expect(badges).toHaveLength(4);

    const pendingBadge = screen.getByText("pending");
    const activeBadge = screen.getByText("active");
    const completedBadge = screen.getByText("completed");
    const revokedBadge = screen.getByText("revoked");

    expect(pendingBadge).toBeInTheDocument();
    expect(activeBadge).toBeInTheDocument();
    expect(completedBadge).toBeInTheDocument();
    expect(revokedBadge).toBeInTheDocument();
  });

  it("shows agent_id when present on task", async () => {
    mockApiClient.mockResolvedValueOnce([pendingTask]);
    render(<TasksPage />);

    await waitFor(() => {
      expect(screen.getByText("Process invoices")).toBeInTheDocument();
    });

    expect(
      screen.getByText(/Agent: agent-alpha/)
    ).toBeInTheDocument();
  });

  it("shows non-ApiError message on generic failure", async () => {
    mockApiClient.mockRejectedValueOnce(new TypeError("fetch failed"));

    render(<TasksPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });
    expect(screen.getByText("Failed to load tasks")).toBeInTheDocument();
  });
});
