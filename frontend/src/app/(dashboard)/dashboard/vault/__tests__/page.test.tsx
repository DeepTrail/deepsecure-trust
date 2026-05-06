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

import VaultPage from "../page";
import { apiClient, ApiError } from "@/lib/api/client";

const mockApiClient = apiClient as ReturnType<typeof vi.fn>;

const secretWithService = {
  name: "NOTION_API_KEY",
  service: "notion",
  created_at: "2026-01-15T10:00:00Z",
  updated_at: "2026-03-20T14:30:00Z",
};

const secretWithoutService = {
  name: "OPENAI_KEY",
  created_at: "2026-02-01T08:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("VaultPage", () => {
  it("shows loading skeleton initially", () => {
    mockApiClient.mockReturnValue(new Promise(() => {}));
    render(<VaultPage />);
    expect(screen.getByTestId("page-skeleton")).toBeInTheDocument();
  });

  it("renders secret cards with monospace name and service badge", async () => {
    mockApiClient.mockResolvedValueOnce([secretWithService]);
    render(<VaultPage />);

    await waitFor(() => {
      expect(screen.getByText("NOTION_API_KEY")).toBeInTheDocument();
    });

    const nameElement = screen.getByText("NOTION_API_KEY");
    expect(nameElement).toHaveClass("font-mono");
    expect(screen.getByText("notion")).toBeInTheDocument();
  });

  it("shows EmptyState when no secrets", async () => {
    mockApiClient.mockResolvedValueOnce([]);
    render(<VaultPage />);

    await waitFor(() => {
      expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    });
    expect(screen.getByText("No secrets stored")).toBeInTheDocument();
  });

  it("Store Secret button toggles the create form", async () => {
    mockApiClient.mockResolvedValueOnce([]);
    render(<VaultPage />);

    await waitFor(() => {
      expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Store Secret/i }));

    await waitFor(() => {
      expect(screen.getByLabelText("Name")).toBeInTheDocument();
    });
    expect(screen.getByLabelText("Service")).toBeInTheDocument();
    expect(screen.getByLabelText("Value")).toBeInTheDocument();
  });

  it("create form has name, service, and value (password) fields", async () => {
    mockApiClient.mockResolvedValueOnce([secretWithService]);
    render(<VaultPage />);

    await waitFor(() => {
      expect(screen.getByText("NOTION_API_KEY")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Store Secret/i }));

    await waitFor(() => {
      expect(screen.getByLabelText("Name")).toBeInTheDocument();
    });

    const nameInput = screen.getByLabelText("Name");
    const serviceInput = screen.getByLabelText("Service");
    const valueInput = screen.getByLabelText("Value");

    expect(nameInput).toHaveAttribute("required");
    expect(serviceInput).not.toHaveAttribute("required");
    expect(valueInput).toHaveAttribute("type", "password");
    expect(valueInput).toHaveAttribute("required");
  });

  it("submitting create form calls apiClient POST", async () => {
    mockApiClient
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce(undefined)
      .mockResolvedValueOnce([{ name: "MY_SECRET" }]);

    render(<VaultPage />);

    await waitFor(() => {
      expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Store Secret/i }));

    await waitFor(() => {
      expect(screen.getByLabelText("Name")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "MY_SECRET" },
    });
    fireEvent.change(screen.getByLabelText("Value"), {
      target: { value: "s3cr3t" },
    });
    fireEvent.change(screen.getByLabelText("Service"), {
      target: { value: "github" },
    });

    fireEvent.click(screen.getByRole("button", { name: /^Store$/i }));

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith("vault/store", {
        method: "POST",
        body: JSON.stringify({
          name: "MY_SECRET",
          value: "s3cr3t",
          service: "github",
        }),
      });
    });
  });

  it("delete button shows confirmation dialog", async () => {
    const confirmSpy = vi
      .spyOn(window, "confirm")
      .mockReturnValue(false);

    mockApiClient.mockResolvedValueOnce([secretWithService]);
    render(<VaultPage />);

    await waitFor(() => {
      expect(screen.getByText("NOTION_API_KEY")).toBeInTheDocument();
    });

    const deleteButton = screen.getByRole("button", { name: "" });
    fireEvent.click(deleteButton);

    expect(confirmSpy).toHaveBeenCalledWith(
      "Delete secret 'NOTION_API_KEY'? This cannot be undone."
    );
  });

  it("confirming delete calls apiClient DELETE", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);

    mockApiClient
      .mockResolvedValueOnce([secretWithService])
      .mockResolvedValueOnce(undefined)
      .mockResolvedValueOnce([]);

    render(<VaultPage />);

    await waitFor(() => {
      expect(screen.getByText("NOTION_API_KEY")).toBeInTheDocument();
    });

    const deleteButton = screen.getByRole("button", { name: "" });
    fireEvent.click(deleteButton);

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith(
        "vault/secrets/NOTION_API_KEY",
        { method: "DELETE" }
      );
    });
  });

  it("shows ErrorCard on fetch failure with retry", async () => {
    const { ApiError: MockApiError } = await import("@/lib/api/client");
    mockApiClient.mockRejectedValueOnce(
      new MockApiError(403, "Forbidden")
    );

    render(<VaultPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });
    expect(screen.getByText("Failed to load vault (403)")).toBeInTheDocument();

    mockApiClient.mockResolvedValueOnce([secretWithService]);
    fireEvent.click(screen.getByRole("button", { name: /Retry/i }));

    await waitFor(() => {
      expect(screen.getByText("NOTION_API_KEY")).toBeInTheDocument();
    });
  });

  it("shows updated_at timestamp if present", async () => {
    mockApiClient.mockResolvedValueOnce([secretWithService]);
    render(<VaultPage />);

    await waitFor(() => {
      expect(screen.getByText("NOTION_API_KEY")).toBeInTheDocument();
    });

    expect(
      screen.getByText(
        `Updated: ${new Date("2026-03-20T14:30:00Z").toLocaleDateString()}`
      )
    ).toBeInTheDocument();
  });

  it("handles object-format API response with secrets wrapper", async () => {
    mockApiClient.mockResolvedValueOnce({
      secrets: [secretWithoutService],
    });

    render(<VaultPage />);

    await waitFor(() => {
      expect(screen.getByText("OPENAI_KEY")).toBeInTheDocument();
    });
  });

  it("shows non-ApiError message on generic failure", async () => {
    mockApiClient.mockRejectedValueOnce(new Error("Network error"));

    render(<VaultPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });
    expect(screen.getByText("Failed to load vault")).toBeInTheDocument();
  });

  it("does not show service badge when service is absent", async () => {
    mockApiClient.mockResolvedValueOnce([secretWithoutService]);
    render(<VaultPage />);

    await waitFor(() => {
      expect(screen.getByText("OPENAI_KEY")).toBeInTheDocument();
    });

    expect(screen.queryByText("notion")).not.toBeInTheDocument();
  });

  it("create form requires name and value fields", async () => {
    mockApiClient.mockResolvedValueOnce([]);
    render(<VaultPage />);

    await waitFor(() => {
      expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Store Secret/i }));

    await waitFor(() => {
      expect(screen.getByLabelText("Name")).toBeInTheDocument();
    });

    expect(screen.getByLabelText("Name")).toHaveAttribute("required");
    expect(screen.getByLabelText("Value")).toHaveAttribute("required");
    expect(screen.getByLabelText("Service")).not.toHaveAttribute("required");
  });

  it("re-enables form after create API failure", async () => {
    mockApiClient
      .mockResolvedValueOnce([])
      .mockRejectedValueOnce(new Error("Network error"));

    render(<VaultPage />);

    await waitFor(() => {
      expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Store Secret/i }));

    await waitFor(() => {
      expect(screen.getByLabelText("Name")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "BAD_KEY" },
    });
    fireEvent.change(screen.getByLabelText("Value"), {
      target: { value: "val" },
    });

    fireEvent.click(screen.getByRole("button", { name: /^Store$/i }));

    await waitFor(() => {
      const storeButton = screen.getByRole("button", { name: /^Store$/i });
      expect(storeButton).not.toBeDisabled();
    });
  });
});
