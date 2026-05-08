import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import PoliciesPage from "../page";
import { apiClient } from "@/lib/api/client";

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

const POLICIES = [
  {
    policy_id: "pol-1",
    name: "ReadOnly Policy",
    description: "Grants read-only access to all resources.",
    permissions: ["service:data:read", "service:config:read"],
    agent_ids: ["agent-1", "agent-2"],
    created_at: "2026-01-10T00:00:00Z",
  },
  {
    policy_id: "pol-2",
    name: "Admin Policy",
    permissions: ["service:*:*"],
  },
  {
    policy_id: "pol-3",
    name: "Empty Policy",
  },
];

describe("PoliciesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows loading skeleton initially", () => {
    mockApiClient.mockReturnValue(new Promise(() => {}));
    render(<PoliciesPage />);
    expect(screen.getByTestId("page-skeleton")).toBeInTheDocument();
  });

  it("renders policy cards with name, description, and permissions badges", async () => {
    mockApiClient.mockResolvedValueOnce(POLICIES);
    render(<PoliciesPage />);

    await waitFor(() => {
      expect(screen.getByText("ReadOnly Policy")).toBeInTheDocument();
    });

    expect(screen.getByText("Admin Policy")).toBeInTheDocument();
    expect(screen.getByText("Empty Policy")).toBeInTheDocument();

    expect(
      screen.getByText("Grants read-only access to all resources.")
    ).toBeInTheDocument();

    expect(screen.getByText("service:data:read")).toBeInTheDocument();
    expect(screen.getByText("service:config:read")).toBeInTheDocument();
    expect(screen.getByText("service:*:*")).toBeInTheDocument();
  });

  it("shows EmptyState when there are no policies", async () => {
    mockApiClient.mockResolvedValueOnce([]);
    render(<PoliciesPage />);

    await waitFor(() => {
      expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    });
    expect(screen.getByText("No policies defined")).toBeInTheDocument();
  });

  it("toggles the create form when Create Policy is clicked", async () => {
    mockApiClient.mockResolvedValueOnce(POLICIES);
    render(<PoliciesPage />);

    await waitFor(() => {
      expect(screen.getByText("ReadOnly Policy")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /create policy/i }));
    expect(screen.getByLabelText("Name")).toBeInTheDocument();
    expect(screen.getByLabelText("Description")).toBeInTheDocument();
    expect(screen.getByLabelText(/permissions/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/agent ids/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /create policy/i }));
    expect(screen.queryByLabelText(/permissions/i)).not.toBeInTheDocument();
  });

  it("submits create form with correct payload including comma-split permissions", async () => {
    mockApiClient.mockResolvedValueOnce(POLICIES);
    render(<PoliciesPage />);

    await waitFor(() => {
      expect(screen.getByText("ReadOnly Policy")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /create policy/i }));

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "New Policy" },
    });
    fireEvent.change(screen.getByLabelText("Description"), {
      target: { value: "A new policy" },
    });
    fireEvent.change(screen.getByLabelText(/permissions/i), {
      target: { value: "svc:scope:read, svc:scope:write" },
    });
    fireEvent.change(screen.getByLabelText(/agent ids/i), {
      target: { value: "agent-a, agent-b" },
    });

    mockApiClient.mockResolvedValueOnce(undefined);
    mockApiClient.mockResolvedValueOnce(POLICIES);

    fireEvent.click(screen.getByRole("button", { name: /^create$/i }));

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith("policies/", {
        method: "POST",
        body: JSON.stringify({
          name: "New Policy",
          description: "A new policy",
          permissions: ["svc:scope:read", "svc:scope:write"],
          agent_ids: ["agent-a", "agent-b"],
        }),
      });
    });
  });

  it("omits description and agent_ids when left empty", async () => {
    mockApiClient.mockResolvedValueOnce(POLICIES);
    render(<PoliciesPage />);

    await waitFor(() => {
      expect(screen.getByText("ReadOnly Policy")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /create policy/i }));

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Minimal" },
    });
    fireEvent.change(screen.getByLabelText(/permissions/i), {
      target: { value: "svc:read" },
    });

    mockApiClient.mockResolvedValueOnce(undefined);
    mockApiClient.mockResolvedValueOnce(POLICIES);

    fireEvent.click(screen.getByRole("button", { name: /^create$/i }));

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith("policies/", {
        method: "POST",
        body: JSON.stringify({
          name: "Minimal",
          description: undefined,
          permissions: ["svc:read"],
          agent_ids: undefined,
        }),
      });
    });
  });

  it("shows confirmation dialog on delete and calls API when confirmed", async () => {
    mockApiClient.mockResolvedValueOnce(POLICIES);
    render(<PoliciesPage />);

    await waitFor(() => {
      expect(screen.getByText("ReadOnly Policy")).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByRole("button").filter((btn) => {
      return (
        btn.querySelector("svg.lucide-trash-2") !== null ||
        btn.innerHTML.includes("trash")
      );
    });

    mockApiClient.mockResolvedValueOnce(undefined);
    mockApiClient.mockResolvedValueOnce(POLICIES);

    fireEvent.click(deleteButtons[0]);

    expect(window.confirm).toHaveBeenCalledWith(
      "Are you sure you want to delete this policy?"
    );

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith("policies/pol-1", {
        method: "DELETE",
      });
    });
  });

  it("does not call API when delete confirmation is cancelled", async () => {
    mockApiClient.mockResolvedValueOnce(POLICIES);
    render(<PoliciesPage />);

    await waitFor(() => {
      expect(screen.getByText("ReadOnly Policy")).toBeInTheDocument();
    });

    vi.mocked(window.confirm).mockReturnValueOnce(false);

    const deleteButtons = screen.getAllByRole("button").filter((btn) => {
      return (
        btn.querySelector("svg.lucide-trash-2") !== null ||
        btn.innerHTML.includes("trash")
      );
    });

    fireEvent.click(deleteButtons[0]);

    expect(window.confirm).toHaveBeenCalled();
    expect(mockApiClient).toHaveBeenCalledTimes(1);
  });

  it("shows ErrorCard on fetch failure with retry", async () => {
    const { ApiError } = await import("@/lib/api/client");
    mockApiClient.mockRejectedValueOnce(new ApiError(503, "Service Unavailable"));
    render(<PoliciesPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });

    expect(screen.getByText("Policies")).toBeInTheDocument();
    expect(
      screen.getByText("Failed to load policies (503)")
    ).toBeInTheDocument();

    mockApiClient.mockResolvedValueOnce(POLICIES);
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));

    await waitFor(() => {
      expect(screen.getByText("ReadOnly Policy")).toBeInTheDocument();
    });
  });

  it("shows generic error message for non-ApiError failures", async () => {
    mockApiClient.mockRejectedValueOnce(new TypeError("fetch failed"));
    render(<PoliciesPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });
    expect(screen.getByText("Failed to load policies")).toBeInTheDocument();
  });

  it("displays agent_ids on the policy card", async () => {
    mockApiClient.mockResolvedValueOnce(POLICIES);
    render(<PoliciesPage />);

    await waitFor(() => {
      expect(screen.getByText("ReadOnly Policy")).toBeInTheDocument();
    });

    expect(screen.getByText("Agents: agent-1, agent-2")).toBeInTheDocument();
  });

  it("does not render agent_ids section when absent", async () => {
    mockApiClient.mockResolvedValueOnce([POLICIES[2]]);
    render(<PoliciesPage />);

    await waitFor(() => {
      expect(screen.getByText("Empty Policy")).toBeInTheDocument();
    });

    expect(screen.queryByText(/^Agents:/)).not.toBeInTheDocument();
  });

  it("shows create error for ApiError failures", async () => {
    mockApiClient.mockResolvedValueOnce(POLICIES);
    render(<PoliciesPage />);

    await waitFor(() => {
      expect(screen.getByText("ReadOnly Policy")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /create policy/i }));
    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Bad Policy" },
    });

    const { ApiError } = await import("@/lib/api/client");
    mockApiClient.mockRejectedValueOnce(new ApiError(400, "Bad Request"));

    fireEvent.click(screen.getByRole("button", { name: /^create$/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Failed to create policy (400).")
      ).toBeInTheDocument();
    });
  });

  it("shows generic create error for non-ApiError failures", async () => {
    mockApiClient.mockResolvedValueOnce(POLICIES);
    render(<PoliciesPage />);

    await waitFor(() => {
      expect(screen.getByText("ReadOnly Policy")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /create policy/i }));
    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Fail Policy" },
    });

    mockApiClient.mockRejectedValueOnce(new Error("Network error"));

    fireEvent.click(screen.getByRole("button", { name: /^create$/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Failed to create policy. Please try again.")
      ).toBeInTheDocument();
    });
  });

  it("cancel button in create form hides the form", async () => {
    mockApiClient.mockResolvedValueOnce(POLICIES);
    render(<PoliciesPage />);

    await waitFor(() => {
      expect(screen.getByText("ReadOnly Policy")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /create policy/i }));
    expect(screen.getByLabelText("Name")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));

    await waitFor(() => {
      expect(screen.queryByLabelText(/permissions/i)).not.toBeInTheDocument();
    });
  });

  describe("edit functionality", () => {
    it("clicking edit button shows edit form with pre-filled values", async () => {
      mockApiClient.mockResolvedValueOnce(POLICIES);
      render(<PoliciesPage />);

      await waitFor(() => {
        expect(screen.getByText("ReadOnly Policy")).toBeInTheDocument();
      });

      const editButtons = screen.getAllByRole("button").filter((btn) => {
        return (
          btn.querySelector("svg.lucide-pencil") !== null ||
          btn.innerHTML.includes("pencil")
        );
      });

      fireEvent.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByDisplayValue("ReadOnly Policy")).toBeInTheDocument();
      });
      expect(
        screen.getByDisplayValue("Grants read-only access to all resources.")
      ).toBeInTheDocument();
      expect(
        screen.getByDisplayValue("service:data:read, service:config:read")
      ).toBeInTheDocument();
      expect(
        screen.getByDisplayValue("agent-1, agent-2")
      ).toBeInTheDocument();
    });

    it("submitting edit form calls PUT with correct payload", async () => {
      mockApiClient.mockResolvedValueOnce(POLICIES);
      render(<PoliciesPage />);

      await waitFor(() => {
        expect(screen.getByText("ReadOnly Policy")).toBeInTheDocument();
      });

      const editButtons = screen.getAllByRole("button").filter((btn) => {
        return (
          btn.querySelector("svg.lucide-pencil") !== null ||
          btn.innerHTML.includes("pencil")
        );
      });

      fireEvent.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByDisplayValue("ReadOnly Policy")).toBeInTheDocument();
      });

      fireEvent.change(screen.getByDisplayValue("ReadOnly Policy"), {
        target: { value: "Updated Policy" },
      });

      mockApiClient.mockResolvedValueOnce(undefined);
      mockApiClient.mockResolvedValueOnce(POLICIES);

      fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

      await waitFor(() => {
        expect(mockApiClient).toHaveBeenCalledWith("policies/pol-1", {
          method: "PUT",
          body: JSON.stringify({
            name: "Updated Policy",
            description: "Grants read-only access to all resources.",
            permissions: ["service:data:read", "service:config:read"],
            agent_ids: ["agent-1", "agent-2"],
          }),
        });
      });
    });

    it("cancel button in edit form reverts to card view", async () => {
      mockApiClient.mockResolvedValueOnce(POLICIES);
      render(<PoliciesPage />);

      await waitFor(() => {
        expect(screen.getByText("ReadOnly Policy")).toBeInTheDocument();
      });

      const editButtons = screen.getAllByRole("button").filter((btn) => {
        return (
          btn.querySelector("svg.lucide-pencil") !== null ||
          btn.innerHTML.includes("pencil")
        );
      });

      fireEvent.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByDisplayValue("ReadOnly Policy")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole("button", { name: /cancel/i }));

      await waitFor(() => {
        expect(screen.getByText("ReadOnly Policy")).toBeInTheDocument();
        expect(
          screen.queryByDisplayValue("ReadOnly Policy")
        ).not.toBeInTheDocument();
      });
    });

    it("shows error when edit submission fails", async () => {
      mockApiClient.mockResolvedValueOnce(POLICIES);
      render(<PoliciesPage />);

      await waitFor(() => {
        expect(screen.getByText("ReadOnly Policy")).toBeInTheDocument();
      });

      const editButtons = screen.getAllByRole("button").filter((btn) => {
        return (
          btn.querySelector("svg.lucide-pencil") !== null ||
          btn.innerHTML.includes("pencil")
        );
      });

      fireEvent.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByDisplayValue("ReadOnly Policy")).toBeInTheDocument();
      });

      const { ApiError } = await import("@/lib/api/client");
      mockApiClient.mockRejectedValueOnce(new ApiError(422, "Unprocessable"));

      fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

      await waitFor(() => {
        expect(
          screen.getByText("Failed to update policy (422).")
        ).toBeInTheDocument();
      });
    });
  });
});
