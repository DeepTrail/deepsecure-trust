import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { LifecycleStepper } from "../LifecycleStepper";

describe("LifecycleStepper", () => {
  it("renders all lifecycle steps", () => {
    render(<LifecycleStepper status="requested" />);
    const list = screen.getByRole("list", { name: /task lifecycle/i });
    expect(list).toBeInTheDocument();
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(5);
  });

  it("displays correct step labels for non-terminal status", () => {
    render(<LifecycleStepper status="active" />);
    expect(screen.getByText("pending")).toBeInTheDocument();
    expect(screen.getByText("requested")).toBeInTheDocument();
    expect(screen.getByText("delegated")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();
  });

  it("replaces last step label for terminal 'failed' status", () => {
    render(<LifecycleStepper status="failed" />);
    expect(screen.getByText("pending")).toBeInTheDocument();
    expect(screen.getByText("requested")).toBeInTheDocument();
    expect(screen.getByText("delegated")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("failed")).toBeInTheDocument();
    expect(screen.queryByText("completed")).not.toBeInTheDocument();
  });

  it("replaces last step label for terminal 'revoked' status", () => {
    render(<LifecycleStepper status="revoked" />);
    expect(screen.getByText("revoked")).toBeInTheDocument();
    expect(screen.queryByText("completed")).not.toBeInTheDocument();
  });

  it("displays formatted timestamps when provided", () => {
    render(
      <LifecycleStepper
        status="active"
        timestamps={{
          requested_at: "2026-04-01T09:00:00Z",
          delegated_at: "2026-04-01T10:00:00Z",
        }}
      />
    );
    const timestamps = screen.getAllByText(/Apr/);
    expect(timestamps.length).toBeGreaterThanOrEqual(1);
  });

  it("handles missing timestamps gracefully", () => {
    render(<LifecycleStepper status="completed" timestamps={{}} />);
    expect(screen.getByText("completed")).toBeInTheDocument();
  });

  it("handles unknown status gracefully", () => {
    render(<LifecycleStepper status="unknown_status" />);
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(5);
  });

  it("applies custom className", () => {
    const { container } = render(
      <LifecycleStepper status="active" className="my-custom-class" />
    );
    expect(container.firstChild).toHaveClass("my-custom-class");
  });

  it("marks correct step as current for 'delegated' status", () => {
    render(<LifecycleStepper status="delegated" />);
    const delegatedStep = screen.getByText("delegated");
    expect(delegatedStep).toHaveClass("text-blue-600");
  });

  it("marks earlier steps as completed for 'active' status", () => {
    render(<LifecycleStepper status="active" />);
    const pending = screen.getByText("pending");
    const requested = screen.getByText("requested");
    const delegated = screen.getByText("delegated");
    expect(pending).toHaveClass("text-green-600");
    expect(requested).toHaveClass("text-green-600");
    expect(delegated).toHaveClass("text-green-600");
  });

  it("marks future steps as muted for 'requested' status", () => {
    render(<LifecycleStepper status="requested" />);
    const completed = screen.getByText("completed");
    expect(completed.className).toContain("text-muted-foreground");
  });
});
