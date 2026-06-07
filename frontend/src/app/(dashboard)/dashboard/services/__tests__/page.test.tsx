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

const DEFAULT_SERVICES = [
  {
    service_id: "notion",
    display_name: "Notion",
    description: "Notes",
    backend_type: "rest",
    endpoint_url: "https://api.notion.com",
    status: "active",
    health_status: "up",
    connected: false,
    scopes_granted: [] as string[],
    connected_at: null,
  },
  {
    service_id: "slack",
    display_name: "Slack",
    description: "Chat",
    backend_type: "rest",
    endpoint_url: "https://slack.com/api",
    status: "active",
    health_status: "up",
    connected: false,
    scopes_granted: [] as string[],
    connected_at: null,
  },
  {
    service_id: "gmail",
    display_name: "Gmail",
    description: "Email",
    backend_type: "rest",
    endpoint_url: "https://gmail.googleapis.com",
    status: "active",
    health_status: "up",
    connected: false,
    scopes_granted: [] as string[],
    connected_at: null,
  },
  {
    service_id: "gcalendar",
    display_name: "Google Calendar",
    description: "Calendar",
    backend_type: "rest",
    endpoint_url: "https://calendar.googleapis.com",
    status: "active",
    health_status: "up",
    connected: false,
    scopes_granted: [] as string[],
    connected_at: null,
  },
  {
    service_id: "gdrive",
    display_name: "Google Drive",
    description: "Drive",
    backend_type: "rest",
    endpoint_url: "https://www.googleapis.com/drive",
    status: "active",
    health_status: "up",
    connected: false,
    scopes_granted: [] as string[],
    connected_at: null,
  },
];

function catalogResponse(
  services = DEFAULT_SERVICES,
  overrides?: Partial<(typeof DEFAULT_SERVICES)[number]>[]
) {
  const merged = overrides
    ? services.map((s, i) => ({ ...s, ...(overrides[i] ?? {}) }))
    : services;
  return { services: merged, total: merged.length };
}

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
    mockApiClient.mockResolvedValueOnce(
      catalogResponse(
        DEFAULT_SERVICES.map((s) =>
          s.service_id === "notion"
            ? { ...s, connected: true, scopes_granted: ["read", "write"] }
            : s
        )
      )
    );
    render(<ServicesPage />);

    await waitFor(() => {
      expect(screen.getByText("Notion")).toBeInTheDocument();
    });

    expect(screen.getByText("Slack")).toBeInTheDocument();
    expect(screen.getByText("Gmail")).toBeInTheDocument();
    expect(screen.getByText("Connected")).toBeInTheDocument();
  });

  it("shows 'Not Connected' badge for unconnected services", async () => {
    mockApiClient.mockResolvedValueOnce(catalogResponse());
    render(<ServicesPage />);

    await waitFor(() => {
      expect(screen.getByText("Notion")).toBeInTheDocument();
    });

    const notConnected = screen.getAllByText("Not Connected");
    expect(notConnected.length).toBe(5);
  });

  it("shows ErrorCard on fetch failure with retry", async () => {
    mockApiClient.mockRejectedValueOnce(new ApiError(500, "Internal Server Error"));

    render(<ServicesPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });
    expect(screen.getByText("Failed to load services (500)")).toBeInTheDocument();

    mockApiClient.mockResolvedValueOnce(catalogResponse());
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
    mockApiClient.mockResolvedValueOnce(catalogResponse());
    render(<ServicesPage />);

    await waitFor(() => {
      expect(screen.getByText("Notion")).toBeInTheDocument();
    });

    const connectButtons = screen.getAllByRole("button", { name: /Connect/i });
    expect(connectButtons.length).toBe(5);
  });

  it("renders Disconnect button for connected services", async () => {
    mockApiClient.mockResolvedValueOnce(
      catalogResponse(
        DEFAULT_SERVICES.map((s) =>
          s.service_id === "notion" ? { ...s, connected: true, scopes_granted: [] } : s
        )
      )
    );
    render(<ServicesPage />);

    await waitFor(() => {
      expect(screen.getByText("Notion")).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: /Disconnect/i })).toBeInTheDocument();
  });

  it("shows scopes for connected services", async () => {
    mockApiClient.mockResolvedValueOnce(
      catalogResponse(
        DEFAULT_SERVICES.map((s) =>
          s.service_id === "notion"
            ? { ...s, connected: true, scopes_granted: ["read", "write"] }
            : s
        )
      )
    );
    render(<ServicesPage />);

    await waitFor(() => {
      expect(screen.getByText("read")).toBeInTheDocument();
    });
    expect(screen.getByText("write")).toBeInTheDocument();
  });

  it("disconnect button shows confirmation dialog first", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);

    mockApiClient.mockResolvedValueOnce(
      catalogResponse(
        DEFAULT_SERVICES.map((s) =>
          s.service_id === "notion" ? { ...s, connected: true, scopes_granted: [] } : s
        )
      )
    );
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
    mockApiClient.mockResolvedValueOnce(catalogResponse());
    const { container } = render(<ServicesPage />);

    await waitFor(() => {
      expect(screen.getByText("Notion")).toBeInTheDocument();
    });

    const grid = container.querySelector(".grid");
    expect(grid).toHaveClass("lg:grid-cols-3");
  });

  it("renders page title and description", async () => {
    mockApiClient.mockResolvedValueOnce(catalogResponse());
    render(<ServicesPage />);

    await waitFor(() => {
      expect(screen.getByText("Service Connections")).toBeInTheDocument();
    });
  });
});
