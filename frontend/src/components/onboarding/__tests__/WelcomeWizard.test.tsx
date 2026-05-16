import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

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

import { WelcomeWizard } from "../WelcomeWizard";
import { StepIndicator } from "../StepIndicator";
import { apiClient } from "@/lib/api/client";

const mockApiClient = vi.mocked(apiClient);

describe("WelcomeWizard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the welcome step initially", () => {
    render(<WelcomeWizard />);
    expect(screen.getAllByText("Welcome").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Welcome to DeepSecure/)).toBeInTheDocument();
    expect(screen.getByText(/Trust Model/)).toBeInTheDocument();
  });

  it("shows all step labels in the indicator", () => {
    render(<WelcomeWizard />);
    const nav = screen.getByRole("navigation", { name: /onboarding progress/i });
    expect(nav).toBeInTheDocument();
    expect(screen.getAllByText("Welcome").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Connect Service").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Register Agent").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Create Delegation").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Complete").length).toBeGreaterThanOrEqual(1);
  });

  it("navigates forward on Next click", () => {
    render(<WelcomeWizard />);
    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    expect(screen.getByText(/DeepSecure supports the following services/)).toBeInTheDocument();
  });

  it("navigates backward on Back click", () => {
    render(<WelcomeWizard />);
    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    expect(screen.getByText(/DeepSecure supports the following services/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /back/i }));
    expect(screen.getByText(/Welcome to DeepSecure/)).toBeInTheDocument();
  });

  it("disables Back button on the first step", () => {
    render(<WelcomeWizard />);
    const backButton = screen.getByRole("button", { name: /back/i });
    expect(backButton).toBeDisabled();
  });

  it("can navigate through all steps", () => {
    render(<WelcomeWizard />);

    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    expect(screen.getByText(/DeepSecure supports the following services/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    expect(screen.getByText(/Register an AI agent/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    expect(screen.getByText(/Create a delegation/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    expect(screen.getByText(/You're all set/)).toBeInTheDocument();
  });

  it("shows 'Go to Dashboard' button on the final step", () => {
    render(<WelcomeWizard />);

    for (let i = 0; i < 4; i++) {
      fireEvent.click(screen.getByRole("button", { name: /next/i }));
    }

    expect(screen.getByRole("button", { name: /go to dashboard/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^next$/i })).not.toBeInTheDocument();
  });

  it("calls onComplete after successful completion", async () => {
    const onComplete = vi.fn();
    mockApiClient.mockResolvedValue(undefined as never);

    render(<WelcomeWizard onComplete={onComplete} />);

    for (let i = 0; i < 4; i++) {
      fireEvent.click(screen.getByRole("button", { name: /next/i }));
    }

    fireEvent.click(screen.getByRole("button", { name: /go to dashboard/i }));

    await waitFor(() => {
      expect(onComplete).toHaveBeenCalledTimes(1);
    });

    expect(mockApiClient).toHaveBeenCalledWith("users/me", {
      method: "PATCH",
      body: JSON.stringify({ onboarding_completed: true }),
    });
  });

  it("shows error message when completion fails", async () => {
    mockApiClient.mockRejectedValue(new Error("Network error"));

    render(<WelcomeWizard />);

    for (let i = 0; i < 4; i++) {
      fireEvent.click(screen.getByRole("button", { name: /next/i }));
    }

    fireEvent.click(screen.getByRole("button", { name: /go to dashboard/i }));

    await waitFor(() => {
      expect(screen.getByText(/Failed to complete onboarding/)).toBeInTheDocument();
    });
  });

  it("disables the complete button while submitting", async () => {
    mockApiClient.mockImplementation(() => new Promise(() => {}));

    render(<WelcomeWizard />);

    for (let i = 0; i < 4; i++) {
      fireEvent.click(screen.getByRole("button", { name: /next/i }));
    }

    const completeBtn = screen.getByRole("button", { name: /go to dashboard/i });
    fireEvent.click(completeBtn);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /finishing/i })).toBeDisabled();
    });
  });
});

describe("StepIndicator", () => {
  const steps = [
    { id: "step-1", label: "First" },
    { id: "step-2", label: "Second" },
    { id: "step-3", label: "Third" },
  ];

  it("renders all step labels", () => {
    render(<StepIndicator steps={steps} currentStep={0} />);
    expect(screen.getByText("First")).toBeInTheDocument();
    expect(screen.getByText("Second")).toBeInTheDocument();
    expect(screen.getByText("Third")).toBeInTheDocument();
  });

  it("marks current step with aria-current", () => {
    render(<StepIndicator steps={steps} currentStep={1} />);
    const currentStepEl = screen.getByText("2").closest("[aria-current]");
    expect(currentStepEl).toHaveAttribute("aria-current", "step");
  });

  it("shows check icon for completed steps", () => {
    const { container } = render(<StepIndicator steps={steps} currentStep={2} />);
    const checkIcons = container.querySelectorAll("svg");
    expect(checkIcons.length).toBeGreaterThanOrEqual(2);
  });

  it("renders step numbers for non-completed steps", () => {
    render(<StepIndicator steps={steps} currentStep={0} />);
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("has a nav element with accessible label", () => {
    render(<StepIndicator steps={steps} currentStep={0} />);
    const nav = screen.getByRole("navigation", { name: /onboarding progress/i });
    expect(nav).toBeInTheDocument();
  });
});
