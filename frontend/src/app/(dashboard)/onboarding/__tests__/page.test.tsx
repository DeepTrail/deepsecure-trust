import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const mockPush = vi.fn();
const mockReplace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace }),
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number;
    statusText: string;
    constructor(status: number, statusText: string) {
      super(`API error: ${status} ${statusText}`);
      this.name = "ApiError";
      this.status = status;
      this.statusText = statusText;
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

import OnboardingPage from "../page";
import { apiClient } from "@/lib/api/client";

const mockApiClient = vi.mocked(apiClient);

describe("OnboardingPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading skeleton initially", () => {
    mockApiClient.mockReturnValue(new Promise(() => {}) as never);
    render(<OnboardingPage />);
    expect(screen.getByTestId("page-skeleton")).toBeInTheDocument();
  });

  it("renders wizard when onboarding is not completed", async () => {
    mockApiClient.mockResolvedValue({ onboarding_completed: false } as never);
    render(<OnboardingPage />);

    await waitFor(() => {
      expect(screen.getByText("Get Started with DeepSecure")).toBeInTheDocument();
    });

    expect(screen.getByText(/Welcome to DeepSecure/)).toBeInTheDocument();
  });

  it("redirects to dashboard when onboarding is already completed", async () => {
    mockApiClient.mockResolvedValue({ onboarding_completed: true } as never);
    render(<OnboardingPage />);

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/dashboard");
    });
  });

  it("shows error card on API failure", async () => {
    mockApiClient.mockRejectedValue(new Error("Network error"));
    render(<OnboardingPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });

    expect(
      screen.getByText("Failed to load onboarding. Please try again.")
    ).toBeInTheDocument();
  });

  it("retries loading on error retry", async () => {
    mockApiClient.mockRejectedValueOnce(new Error("Network error"));
    render(<OnboardingPage />);

    await waitFor(() => {
      expect(screen.getByTestId("error-card")).toBeInTheDocument();
    });

    mockApiClient.mockResolvedValueOnce({ onboarding_completed: false } as never);

    const retryBtn = screen.getByRole("button", { name: /retry/i });
    retryBtn.click();

    await waitFor(() => {
      expect(screen.getByText("Get Started with DeepSecure")).toBeInTheDocument();
    });
  });

  it("page title and description are displayed", async () => {
    mockApiClient.mockResolvedValue({ onboarding_completed: false } as never);
    render(<OnboardingPage />);

    await waitFor(() => {
      expect(screen.getByText("Get Started with DeepSecure")).toBeInTheDocument();
    });

    expect(
      screen.getByText(/Follow these steps to set up/)
    ).toBeInTheDocument();
  });
});
