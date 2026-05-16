import { describe, it, expect, vi } from "vitest";
import { redirect } from "next/navigation";
import Page from "./page";

vi.mock("next/navigation", () => ({
  redirect: vi.fn(),
}));

describe("Landing Page", () => {
  it("redirects to /login", () => {
    Page();
    expect(redirect).toHaveBeenCalledWith("/login");
  });
});
