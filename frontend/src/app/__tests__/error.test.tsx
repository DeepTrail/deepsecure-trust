import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import AppError from "../error";
import DashboardError from "../(dashboard)/error";
import AuthError from "../(auth)/error";

describe("Error Boundaries", () => {
  const mockError = new Error("Test error message");
  const mockReset = vi.fn();

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe("App Error", () => {
    it("renders error message", () => {
      render(<AppError error={mockError} reset={mockReset} />);
      expect(screen.getByText("Test error message")).toBeInTheDocument();
      expect(screen.getByText("Application Error")).toBeInTheDocument();
    });

    it("calls reset on retry", () => {
      render(<AppError error={mockError} reset={mockReset} />);
      fireEvent.click(screen.getByRole("button", { name: /try again/i }));
      expect(mockReset).toHaveBeenCalledOnce();
    });
  });

  describe("Dashboard Error", () => {
    it("renders dashboard-specific error", () => {
      render(<DashboardError error={mockError} reset={mockReset} />);
      expect(screen.getByText("Dashboard Error")).toBeInTheDocument();
      expect(screen.getByText("Test error message")).toBeInTheDocument();
    });

    it("calls reset on retry", () => {
      render(<DashboardError error={mockError} reset={mockReset} />);
      fireEvent.click(screen.getByRole("button", { name: /try again/i }));
      expect(mockReset).toHaveBeenCalledOnce();
    });
  });

  describe("Auth Error", () => {
    it("renders auth-specific error", () => {
      render(<AuthError error={mockError} reset={mockReset} />);
      expect(screen.getByText("Authentication Error")).toBeInTheDocument();
      expect(screen.getByText("Test error message")).toBeInTheDocument();
    });

    it("calls reset on retry", () => {
      render(<AuthError error={mockError} reset={mockReset} />);
      fireEvent.click(screen.getByRole("button", { name: /try again/i }));
      expect(mockReset).toHaveBeenCalledOnce();
    });
  });

  describe("fallback messages", () => {
    it("shows default message when error.message is empty", () => {
      const emptyError = new Error();
      render(<AppError error={emptyError} reset={mockReset} />);
      expect(
        screen.getByText("An unexpected error occurred")
      ).toBeInTheDocument();
    });
  });
});
