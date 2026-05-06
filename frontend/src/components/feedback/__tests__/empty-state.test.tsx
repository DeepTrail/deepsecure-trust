import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EmptyState } from "../empty-state";

describe("EmptyState", () => {
  it("renders the title", () => {
    render(<EmptyState title="No agents found" />);
    expect(screen.getByText("No agents found")).toBeInTheDocument();
  });

  it("renders the description when provided", () => {
    render(
      <EmptyState
        title="No data"
        description="Create your first agent to get started"
      />
    );
    expect(
      screen.getByText("Create your first agent to get started")
    ).toBeInTheDocument();
  });

  it("renders action button when action prop is provided", () => {
    const onClick = vi.fn();
    render(
      <EmptyState
        title="Empty"
        action={{ label: "Create Agent", onClick }}
      />
    );
    const button = screen.getByRole("button", { name: /create agent/i });
    expect(button).toBeInTheDocument();
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("does not render action button when action prop is omitted", () => {
    render(<EmptyState title="Empty" />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("renders custom icon when provided", () => {
    render(
      <EmptyState
        title="Custom"
        icon={<span data-testid="custom-icon">🎯</span>}
      />
    );
    expect(screen.getByTestId("custom-icon")).toBeInTheDocument();
  });
});
