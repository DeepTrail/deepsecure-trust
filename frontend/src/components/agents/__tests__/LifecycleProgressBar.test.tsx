import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { LifecycleProgressBar } from "../LifecycleProgressBar";

describe("LifecycleProgressBar", () => {
  it("renders all four step labels", () => {
    render(<LifecycleProgressBar state="registered" />);

    expect(screen.getByText("Registered")).toBeInTheDocument();
    expect(screen.getByText("Delegated")).toBeInTheDocument();
    expect(screen.getByText("Authenticated")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("highlights only the first step when state is 'registered'", () => {
    const { container } = render(
      <LifecycleProgressBar state="registered" />
    );

    const circles = container.querySelectorAll(".h-8.w-8.rounded-full");
    expect(circles).toHaveLength(4);

    expect(circles[0].className).toContain("bg-primary");
    expect(circles[1].className).not.toContain("bg-primary");
    expect(circles[2].className).not.toContain("bg-primary");
    expect(circles[3].className).not.toContain("bg-primary");
  });

  it("highlights first three steps when state is 'authenticated'", () => {
    const { container } = render(
      <LifecycleProgressBar state="authenticated" />
    );

    const circles = container.querySelectorAll(".h-8.w-8.rounded-full");

    expect(circles[0].className).toContain("bg-primary");
    expect(circles[1].className).toContain("bg-primary");
    expect(circles[2].className).toContain("bg-primary");
    expect(circles[3].className).not.toContain("bg-primary");
  });

  it("highlights all four steps when state is 'active'", () => {
    const { container } = render(
      <LifecycleProgressBar state="active" />
    );

    const circles = container.querySelectorAll(".h-8.w-8.rounded-full");
    expect(circles).toHaveLength(4);
    for (const circle of circles) {
      expect(circle.className).toContain("bg-primary");
    }
  });

  it("applies ring class to the current step", () => {
    const { container } = render(
      <LifecycleProgressBar state="delegated" />
    );

    const circles = container.querySelectorAll(".h-8.w-8.rounded-full");

    expect(circles[1].className).toContain("ring-2");
    expect(circles[0].className).not.toContain("ring-2");
  });

  it("renders connector lines between steps", () => {
    const { container } = render(
      <LifecycleProgressBar state="registered" />
    );

    const connectors = container.querySelectorAll(
      ".h-0\\.5"
    );
    expect(connectors).toHaveLength(3);
  });

  it("applies custom className to root", () => {
    const { container } = render(
      <LifecycleProgressBar state="active" className="mt-4" />
    );
    expect((container.firstChild as HTMLElement).className).toContain("mt-4");
  });
});
