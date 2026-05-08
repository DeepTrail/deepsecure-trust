import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ScopedPermissions, Permission } from "../ScopedPermissions";

const samplePermissions: Permission[] = [
  { service: "notion", scope: "pages", action: "read" },
  { service: "github", scope: "repos", action: "write" },
  { service: "slack", scope: "messages", action: "send", attenuated: true },
];

describe("ScopedPermissions", () => {
  it("renders a table with correct headers", () => {
    render(<ScopedPermissions permissions={samplePermissions} />);
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText("Service")).toBeInTheDocument();
    expect(screen.getByText("Scope")).toBeInTheDocument();
    expect(screen.getByText("Action")).toBeInTheDocument();
    expect(screen.getByText("Source")).toBeInTheDocument();
  });

  it("renders all permission rows", () => {
    render(<ScopedPermissions permissions={samplePermissions} />);
    expect(screen.getByText("notion")).toBeInTheDocument();
    expect(screen.getByText("github")).toBeInTheDocument();
    expect(screen.getByText("slack")).toBeInTheDocument();
    expect(screen.getByText("pages")).toBeInTheDocument();
    expect(screen.getByText("repos")).toBeInTheDocument();
    expect(screen.getByText("messages")).toBeInTheDocument();
  });

  it("shows 'Delegation' badge for non-attenuated permissions", () => {
    render(<ScopedPermissions permissions={[samplePermissions[0]]} />);
    expect(screen.getByText("Delegation")).toBeInTheDocument();
    expect(screen.queryByText("Attenuated")).not.toBeInTheDocument();
  });

  it("shows 'Attenuated' badge for attenuated permissions", () => {
    render(<ScopedPermissions permissions={[samplePermissions[2]]} />);
    expect(screen.getByText("Attenuated")).toBeInTheDocument();
  });

  it("shows empty state when no permissions", () => {
    render(<ScopedPermissions permissions={[]} />);
    expect(
      screen.getByText("No permissions assigned to this task.")
    ).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("applies custom className", () => {
    const { container } = render(
      <ScopedPermissions permissions={[]} className="my-class" />
    );
    expect(container.firstChild).toHaveClass("my-class");
  });

  it("displays mixed delegation and attenuated permissions", () => {
    render(<ScopedPermissions permissions={samplePermissions} />);
    const delegationBadges = screen.getAllByText("Delegation");
    const attenuatedBadges = screen.getAllByText("Attenuated");
    expect(delegationBadges).toHaveLength(2);
    expect(attenuatedBadges).toHaveLength(1);
  });
});
