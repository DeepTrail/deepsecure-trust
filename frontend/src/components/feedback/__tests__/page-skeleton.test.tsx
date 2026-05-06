import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PageSkeleton } from "../page-skeleton";

describe("PageSkeleton", () => {
  it("renders dashboard variant by default", () => {
    const { container } = render(<PageSkeleton />);
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders detail variant", () => {
    const { container } = render(<PageSkeleton variant="detail" />);
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders list variant", () => {
    const { container } = render(<PageSkeleton variant="list" />);
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("applies custom className", () => {
    const { container } = render(<PageSkeleton className="my-custom" />);
    expect(container.firstChild).toHaveClass("my-custom");
  });
});
