// @vitest-environment node
import { describe, it, expect } from "vitest";
import { isTokenNearExpiry } from "../refresh";

function makeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.fake-signature`;
}

describe("isTokenNearExpiry", () => {
  it("returns false for token with >5 min remaining", () => {
    const exp = Math.floor(Date.now() / 1000) + 600; // 10 min
    expect(isTokenNearExpiry(makeJwt({ exp }))).toBe(false);
  });

  it("returns true for token with <5 min remaining", () => {
    const exp = Math.floor(Date.now() / 1000) + 120; // 2 min
    expect(isTokenNearExpiry(makeJwt({ exp }))).toBe(true);
  });

  it("returns false for already-expired token", () => {
    const exp = Math.floor(Date.now() / 1000) - 60; // expired 1 min ago
    expect(isTokenNearExpiry(makeJwt({ exp }))).toBe(false);
  });

  it("returns false for token without exp claim", () => {
    expect(isTokenNearExpiry(makeJwt({ sub: "user" }))).toBe(false);
  });

  it("returns false for malformed JWT", () => {
    expect(isTokenNearExpiry("not-a-jwt")).toBe(false);
    expect(isTokenNearExpiry("")).toBe(false);
  });

  it("returns true at exactly 4 min 59 sec boundary", () => {
    const exp = Math.floor(Date.now() / 1000) + 299; // 4m59s
    expect(isTokenNearExpiry(makeJwt({ exp }))).toBe(true);
  });

  it("returns false at exactly 5 min boundary", () => {
    const exp = Math.floor(Date.now() / 1000) + 300; // exactly 5 min
    expect(isTokenNearExpiry(makeJwt({ exp }))).toBe(false);
  });
});
