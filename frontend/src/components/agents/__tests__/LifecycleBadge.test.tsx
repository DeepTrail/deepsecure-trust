import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { LifecycleBadge, type LifecycleState } from "../LifecycleBadge";

describe("LifecycleBadge", () => {
  const STATES: { state: LifecycleState; label: string }[] = [
    { state: "registered", label: "Registered" },
    { state: "delegated", label: "Delegated" },
    { state: "authenticated", label: "Authenticated" },
    { state: "active", label: "Active" },
  ];

  it.each(STATES)("renders '$label' for state '$state'", ({ state, label }) => {
    render(<LifecycleBadge state={state} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it("renders an icon inside the badge", () => {
    const { container } = render(<LifecycleBadge state="active" />);
    const svgIcon = container.querySelector("svg");
    expect(svgIcon).toBeTruthy();
  });

  it("falls back to 'Registered' for an unknown state", () => {
    render(<LifecycleBadge state={"bogus" as LifecycleState} />);
    expect(screen.getByText("Registered")).toBeInTheDocument();
  });

  it("applies custom className", () => {
    const { container } = render(
      <LifecycleBadge state="delegated" className="my-custom" />
    );
    const badge = container.firstChild as HTMLElement;
    expect(badge.className).toContain("my-custom");
  });

  it("renders as an inline badge element", () => {
    const { container } = render(<LifecycleBadge state="authenticated" />);
    const badge = container.firstChild as HTMLElement;
    expect(badge.className).toContain("flex");
    expect(badge.className).toContain("items-center");
  });
});
