// @vitest-environment node
import { describe, it, expect } from "vitest";
import { generateCsrfToken } from "../csrf";

describe("CSRF helpers", () => {
  it("generates a UUID-format token", () => {
    const token = generateCsrfToken();
    expect(token).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
    );
  });

  it("generates unique tokens", () => {
    const tokens = new Set(Array.from({ length: 10 }, () => generateCsrfToken()));
    expect(tokens.size).toBe(10);
  });
});
