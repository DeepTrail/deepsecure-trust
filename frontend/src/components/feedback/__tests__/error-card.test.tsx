import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ErrorCard } from "../error-card";

describe("ErrorCard", () => {
  it("renders the error message", () => {
    render(<ErrorCard message="Something broke" />);
    expect(screen.getByText("Something broke")).toBeInTheDocument();
  });

  it("renders default title", () => {
    render(<ErrorCard message="Error" />);
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });

  it("renders custom title", () => {
    render(<ErrorCard title="Network Error" message="Timeout" />);
    expect(screen.getByText("Network Error")).toBeInTheDocument();
  });

  it("renders retry button when retry prop is provided", () => {
    const retry = vi.fn();
    render(<ErrorCard message="Error" retry={retry} />);
    const button = screen.getByRole("button", { name: /try again/i });
    expect(button).toBeInTheDocument();
    fireEvent.click(button);
    expect(retry).toHaveBeenCalledOnce();
  });

  it("does not render retry button when retry prop is omitted", () => {
    render(<ErrorCard message="Error" />);
    expect(
      screen.queryByRole("button", { name: /try again/i })
    ).not.toBeInTheDocument();
  });
});
