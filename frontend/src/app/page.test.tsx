import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import Page from "./page";

describe("Landing Page", () => {
  it("renders the page heading", () => {
    render(<Page />);
    expect(screen.getByRole("heading")).toBeInTheDocument();
    expect(screen.getByRole("heading")).toHaveTextContent("DeepSecure");
  });

  it("renders sign in and demo links", () => {
    render(<Page />);
    expect(screen.getByRole("link", { name: /sign in/i })).toHaveAttribute(
      "href",
      "/login"
    );
    expect(
      screen.getByRole("link", { name: /interactive demo/i })
    ).toHaveAttribute("href", "/demo");
  });
});
