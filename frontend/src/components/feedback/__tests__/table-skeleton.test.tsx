import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { TableSkeleton } from "../table-skeleton";

describe("TableSkeleton", () => {
  it("renders with default 5 rows and 5 columns", () => {
    const { container } = render(<TableSkeleton />);
    const allSkeletons = container.querySelectorAll(".animate-pulse");
    // 5 header cols + 5 rows * 5 cols = 30 skeletons
    expect(allSkeletons.length).toBe(30);
  });

  it("renders with custom rows and columns", () => {
    const { container } = render(<TableSkeleton columns={3} rows={2} />);
    const allSkeletons = container.querySelectorAll(".animate-pulse");
    // 3 header cols + 2 rows * 3 cols = 9 skeletons
    expect(allSkeletons.length).toBe(9);
  });

  it("applies custom className", () => {
    const { container } = render(<TableSkeleton className="my-table" />);
    expect(container.firstChild).toHaveClass("my-table");
  });
});
