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

import ServicesPage from "../page";
import { apiClient, ApiError } from "@/lib/api/client";

const mockApiClient = apiClient as ReturnType<typeof vi.fn>;

const connectedService = {
  service_id: "notion",
  service_name: "Notion",
  description: "Workspace management",
  connected: true,
  scopes: ["read", "write"],
};

const disconnectedService = {
  service_id: "slack",
  service_name: "Slack",
  connected: false,
  scopes: ["chat:write"],
};

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ServicesPage", () => {
  it("shows loading skeleton initially", () => {
    mockApiClient.mockReturnValue(new Promise(() => {}));
    render(<ServicesPage />);
    expect(screen.getByTestId("page-skeleton")).toBeInTheDocument();
  });

  it("renders service cards with name, status badge, and scopes", async () => {
    mockApiClient.mockResolvedValueOnce([connectedService, disconnectedService]);
    render(<ServicesPage />);

    await waitFor(() => {
      expect(screen.getByText("Notion")).toBeInTheDocument();
    });

    expect(screen.getByText("Slack")).toBeInTheDocument();
    expect(screen.getByText("Connected")).toBeInTheDocument();
    expect(screen.getByText("Not connected")).toBeInTheDocument();
    expect(screen.getByText("read")).toBeInTheDocument();
    expect(screen.getByText("write")).toBeInTheDocument();
    expect(screen.getByText("chat:write")).toBeInTheDocument();
  });

  it("shows EmptyState when no services", async () => {
    mockApiClient.mockResolvedValueOnce([]);
    render(<ServicesPage />);

    await waitFor(() => {
      expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    });
    expect(screen.getByText("No services available")).toBeInTheDocument();
  });

  it("connect button calls apiClient POST", async () => {
    mockApiClient
      .mockResolvedValueOnce([disconnectedService])
      .mockResolvedValueOnce(undefined)
      .mockResolvedValueOnce([{ ...disconnectedService, connected: true }]);

    render(<ServicesPage />);

    await waitFor(() => {
      expect(screen.getByText("Slack")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Connect/i }));

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith("users/me/services/connect", {
        method: "POST",
        body: JSON.stringify({ service_id: "slack" }),
      });
    });
  });

  it("disconnect button shows confirmation dialog first", async () => {
    const confirmSpy = vi
      .spyOn(window, "confirm")
      .mockReturnValue(false);

    mockApiClient.mockResolvedValueOnce([connectedService]);
    render(<ServicesPage />);

    await waitFor(() => {
      expect(screen.getByText("Notion")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Disconnect/i }));

    expect(confirmSpy).toHaveBeenCalledWith(
      "Disconnect from Notion? This will revoke access."
    );
  });

  it("cancelling disconnect does not call API", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);

    mockApiClient.mockResolvedValueOnce([connectedService]);
    render(<ServicesPage />);

    await waitFor(() => {
      expect(screen.getByText("Notion")).toBeInTheDocument();
    });

    const callCountBefore = mockApiClient.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: /Disconnect/i }));

    expect(mockApiClient).toHaveBeenCalledTimes(callCountBefore);
  });

  it("confirming disconnect calls apiClient DELETE", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);

    mockApiClient
      .mockResolvedValueOnce([connectedService])
      .mockResolvedValueOnce(undefined)
      .mockResolvedValueOnce([]);

    render(<ServicesPage />);

    await waitFor(() => {
      expect(screen.getByText("Notion")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Disconnect/i }));

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith("users/me/services/notion", {
        method: "DELETE",
      });
    });
  });

  it("shows ErrorCard on fetch failure with retry", async () => {
    const { ApiError: MockApiError } = await import("@/lib/api/client");
    mockApiClient.mockRejectedValueOnce(
      new MockApiError(500, "Internal Server Error")
    );

    render(<ServicesPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });
    expect(
      screen.getByText("Failed to load services (500)")
    ).toBeInTheDocument();

    mockApiClient.mockResolvedValueOnce([connectedService]);
    fireEvent.click(screen.getByRole("button", { name: /Retry/i }));

    await waitFor(() => {
      expect(screen.getByText("Notion")).toBeInTheDocument();
    });
  });

  it("shows description if present on service", async () => {
    mockApiClient.mockResolvedValueOnce([connectedService]);
    render(<ServicesPage />);

    await waitFor(() => {
      expect(screen.getByText("Workspace management")).toBeInTheDocument();
    });
  });

  it("grid uses 3-column layout on large screens", async () => {
    mockApiClient.mockResolvedValueOnce([connectedService, disconnectedService]);
    const { container } = render(<ServicesPage />);

    await waitFor(() => {
      expect(screen.getByText("Notion")).toBeInTheDocument();
    });

    const grid = container.querySelector(".grid");
    expect(grid).toHaveClass("lg:grid-cols-3");
  });

  it("handles object-format API response with services map", async () => {
    mockApiClient.mockResolvedValueOnce({
      services: {
        github: {
          service_name: "GitHub",
          connected: true,
          scopes: ["repo"],
        },
      },
    });

    render(<ServicesPage />);

    await waitFor(() => {
      expect(screen.getByText("GitHub")).toBeInTheDocument();
    });
    expect(screen.getByText("repo")).toBeInTheDocument();
  });

  it("shows non-ApiError message on generic failure", async () => {
    mockApiClient.mockRejectedValueOnce(new TypeError("fetch failed"));
    render(<ServicesPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });
    expect(screen.getByText("Failed to load services")).toBeInTheDocument();
  });

  it("connect error is handled gracefully", async () => {
    mockApiClient
      .mockResolvedValueOnce([disconnectedService])
      .mockRejectedValueOnce(new Error("Connection timeout"))
      .mockResolvedValueOnce([disconnectedService]);

    render(<ServicesPage />);

    await waitFor(() => {
      expect(screen.getByText("Slack")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Connect/i }));

    await waitFor(() => {
      expect(screen.getByText("Slack")).toBeInTheDocument();
    });
  });
});
