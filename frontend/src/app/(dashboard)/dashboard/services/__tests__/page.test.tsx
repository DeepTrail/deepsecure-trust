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

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ replace: vi.fn() }),
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

import ServicesPage from "../page";
import { apiClient, ApiError } from "@/lib/api/client";

const mockApiClient = apiClient as ReturnType<typeof vi.fn>;

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

  it("renders service catalog cards when data loads", async () => {
    mockApiClient.mockResolvedValueOnce({
      services: {
        notion: { connected: true, scopes_granted: ["read", "write"] },
      },
    });
    render(<ServicesPage />);

    await waitFor(() => {
      expect(screen.getByText("Notion")).toBeInTheDocument();
    });

    expect(screen.getByText("Slack")).toBeInTheDocument();
    expect(screen.getByText("Gmail")).toBeInTheDocument();
    expect(screen.getByText("Connected")).toBeInTheDocument();
  });

  it("shows 'Not Connected' badge for unconnected services", async () => {
    mockApiClient.mockResolvedValueOnce({ services: {} });
    render(<ServicesPage />);

    await waitFor(() => {
      expect(screen.getByText("Notion")).toBeInTheDocument();
    });

    const notConnected = screen.getAllByText("Not Connected");
    expect(notConnected.length).toBe(5);
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

    mockApiClient.mockResolvedValueOnce({ services: {} });
    fireEvent.click(screen.getByRole("button", { name: /Retry/i }));

    await waitFor(() => {
      expect(screen.getByText("Notion")).toBeInTheDocument();
    });
  });

  it("shows non-ApiError message on generic failure", async () => {
    mockApiClient.mockRejectedValueOnce(new TypeError("fetch failed"));
    render(<ServicesPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });
    expect(screen.getByText("Failed to load services")).toBeInTheDocument();
  });

  it("renders Connect buttons for unconnected services", async () => {
    mockApiClient.mockResolvedValueOnce({ services: {} });
    render(<ServicesPage />);

    await waitFor(() => {
      expect(screen.getByText("Notion")).toBeInTheDocument();
    });

    const connectButtons = screen.getAllByRole("button", { name: /Connect/i });
    expect(connectButtons.length).toBe(5);
  });

  it("renders Disconnect button for connected services", async () => {
    mockApiClient.mockResolvedValueOnce({
      services: {
        notion: { connected: true, scopes_granted: [] },
      },
    });
    render(<ServicesPage />);

    await waitFor(() => {
      expect(screen.getByText("Notion")).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: /Disconnect/i })).toBeInTheDocument();
  });

  it("shows scopes for connected services", async () => {
    mockApiClient.mockResolvedValueOnce({
      services: {
        notion: { connected: true, scopes_granted: ["read", "write"] },
      },
    });
    render(<ServicesPage />);

    await waitFor(() => {
      expect(screen.getByText("read")).toBeInTheDocument();
    });
    expect(screen.getByText("write")).toBeInTheDocument();
  });

  it("disconnect button shows confirmation dialog first", async () => {
    const confirmSpy = vi
      .spyOn(window, "confirm")
      .mockReturnValue(false);

    mockApiClient.mockResolvedValueOnce({
      services: {
        notion: { connected: true, scopes_granted: [] },
      },
    });
    render(<ServicesPage />);

    await waitFor(() => {
      expect(screen.getByText("Notion")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Disconnect/i }));

    expect(confirmSpy).toHaveBeenCalledWith(
      "Disconnect from Notion? This will revoke access."
    );
  });

  it("grid uses 3-column layout on large screens", async () => {
    mockApiClient.mockResolvedValueOnce({ services: {} });
    const { container } = render(<ServicesPage />);

    await waitFor(() => {
      expect(screen.getByText("Notion")).toBeInTheDocument();
    });

    const grid = container.querySelector(".grid");
    expect(grid).toHaveClass("lg:grid-cols-3");
  });

  it("renders page title and description", async () => {
    mockApiClient.mockResolvedValueOnce({ services: {} });
    render(<ServicesPage />);

    await waitFor(() => {
      expect(screen.getByText("Service Connections")).toBeInTheDocument();
    });
  });
});
