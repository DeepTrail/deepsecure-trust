import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "task-001" }),
  useRouter: () => ({ push: mockPush }),
}));

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

import TaskDetailPage from "../page";
import { apiClient } from "@/lib/api/client";

const mockApiClient = apiClient as ReturnType<typeof vi.fn>;

const fullTask = {
  task_id: "task-001",
  name: "Process invoices",
  description: "Process all pending invoices for Q1",
  status: "active",
  agent_id: "agent-alpha",
  delegation_id: "del-001",
  created_at: "2026-04-01T09:00:00Z",
  completed_at: undefined,
  permissions: [
    { service: "notion", scope: "pages", action: "read" },
    { service: "slack", scope: "messages", action: "send", attenuated: true },
  ],
  token_status: "active",
  token_expires_at: "2030-12-31T23:59:59Z",
};

const pendingTask = {
  task_id: "task-001",
  name: "Waiting task",
  status: "pending",
};

const completedTask = {
  task_id: "task-001",
  name: "Done task",
  status: "completed",
  completed_at: "2026-04-02T15:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("TaskDetailPage", () => {
  it("shows loading skeleton initially", () => {
    mockApiClient.mockReturnValue(new Promise(() => {}));
    render(<TaskDetailPage />);
    expect(screen.getByTestId("page-skeleton")).toBeInTheDocument();
  });

  it("renders task detail with name, status, and description", async () => {
    mockApiClient.mockResolvedValueOnce(fullTask);
    render(<TaskDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("Process invoices")).toBeInTheDocument();
    });
    expect(screen.getAllByText("active").length).toBeGreaterThanOrEqual(1);
    expect(
      screen.getByText("Process all pending invoices for Q1")
    ).toBeInTheDocument();
  });

  it("renders lifecycle stepper", async () => {
    mockApiClient.mockResolvedValueOnce(fullTask);
    render(<TaskDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("Task Lifecycle")).toBeInTheDocument();
    });
    expect(
      screen.getByRole("list", { name: /task lifecycle/i })
    ).toBeInTheDocument();
  });

  it("renders scoped permissions table", async () => {
    mockApiClient.mockResolvedValueOnce(fullTask);
    render(<TaskDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("Scoped Permissions")).toBeInTheDocument();
    });
    expect(screen.getByText("notion")).toBeInTheDocument();
    expect(screen.getByText("slack")).toBeInTheDocument();
    expect(screen.getByText("Attenuated")).toBeInTheDocument();
  });

  it("renders token status with expiry", async () => {
    mockApiClient.mockResolvedValueOnce(fullTask);
    render(<TaskDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("Token Status")).toBeInTheDocument();
    });
    expect(screen.getAllByText("active").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(/remaining/)).toBeInTheDocument();
  });

  it("shows 'No token issued' when token_status is absent", async () => {
    mockApiClient.mockResolvedValueOnce({ ...fullTask, token_status: undefined });
    render(<TaskDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("No token issued")).toBeInTheDocument();
    });
  });

  it("renders agent and delegation details", async () => {
    mockApiClient.mockResolvedValueOnce(fullTask);
    render(<TaskDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("agent-alpha")).toBeInTheDocument();
    });
    expect(screen.getByText("del-001")).toBeInTheDocument();
  });

  it("shows Complete and Revoke buttons for active task", async () => {
    mockApiClient.mockResolvedValueOnce(fullTask);
    render(<TaskDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("Process invoices")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /Complete/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Revoke/i })).toBeInTheDocument();
  });

  it("shows Activate and Revoke buttons for pending task", async () => {
    mockApiClient.mockResolvedValueOnce(pendingTask);
    render(<TaskDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("Waiting task")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /Activate/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Revoke/i })).toBeInTheDocument();
  });

  it("shows no action buttons for completed task", async () => {
    mockApiClient.mockResolvedValueOnce(completedTask);
    render(<TaskDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("Done task")).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: /Activate/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Complete/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Revoke/i })).not.toBeInTheDocument();
  });

  it("complete action calls the correct API endpoint", async () => {
    mockApiClient
      .mockResolvedValueOnce(fullTask)
      .mockResolvedValueOnce(undefined)
      .mockResolvedValueOnce(completedTask);

    render(<TaskDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("Process invoices")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Complete/i }));

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith("tasks/task-001/complete", {
        method: "POST",
      });
    });
  });

  it("revoke action prompts for confirmation", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    mockApiClient.mockResolvedValueOnce(fullTask);
    render(<TaskDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("Process invoices")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Revoke/i }));
    expect(confirmSpy).toHaveBeenCalledWith("Revoke this task?");
  });

  it("shows ErrorCard on fetch failure", async () => {
    const { ApiError: MockApiError } = await import("@/lib/api/client");
    mockApiClient.mockRejectedValueOnce(new MockApiError(404, "Not Found"));

    render(<TaskDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });
    expect(screen.getByText("Failed to load task (404)")).toBeInTheDocument();
  });

  it("shows generic error on non-ApiError failure", async () => {
    mockApiClient.mockRejectedValueOnce(new TypeError("fetch failed"));

    render(<TaskDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });
    expect(screen.getByText("Failed to load task")).toBeInTheDocument();
  });

  it("retry on error card refetches data", async () => {
    const { ApiError: MockApiError } = await import("@/lib/api/client");
    mockApiClient.mockRejectedValueOnce(new MockApiError(500, "Server Error"));

    render(<TaskDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });

    mockApiClient.mockResolvedValueOnce(fullTask);
    fireEvent.click(screen.getByRole("button", { name: /Retry/i }));

    await waitFor(() => {
      expect(screen.getByText("Process invoices")).toBeInTheDocument();
    });
  });

  it("back button navigates to tasks list", async () => {
    mockApiClient.mockResolvedValueOnce(fullTask);
    render(<TaskDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("Process invoices")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Back to Tasks/i }));
    expect(mockPush).toHaveBeenCalledWith("/dashboard/tasks");
  });

  it("shows task ID in the detail view", async () => {
    mockApiClient.mockResolvedValueOnce(fullTask);
    render(<TaskDetailPage />);

    await waitFor(() => {
      expect(screen.getByText(/task-001/)).toBeInTheDocument();
    });
  });

  it("renders empty permissions state when no permissions", async () => {
    mockApiClient.mockResolvedValueOnce({ ...fullTask, permissions: [] });
    render(<TaskDetailPage />);

    await waitFor(() => {
      expect(
        screen.getByText("No permissions assigned to this task.")
      ).toBeInTheDocument();
    });
  });
});
