// @vitest-environment node
import { describe, it, expect, beforeAll, afterAll, vi } from "vitest";
import { encryptSession, decryptSession } from "../cookie";
import crypto from "crypto";

const TEST_SECRET = crypto.randomBytes(32).toString("hex");

describe("cookie encryption", () => {
  beforeAll(() => {
    vi.stubEnv("SESSION_SECRET", TEST_SECRET);
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("encrypts a JWT into a JWE string", async () => {
    const jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.signature";
    const encrypted = await encryptSession(jwt);
    expect(typeof encrypted).toBe("string");
    expect(encrypted).toContain(".");
    expect(encrypted).not.toBe(jwt);
  });

  it("decrypts back to the original JWT (round-trip)", async () => {
    const jwt = "my-test-jwt-token-12345";
    const encrypted = await encryptSession(jwt);
    const decrypted = await decryptSession(encrypted);
    expect(decrypted).toBe(jwt);
  });

  it("returns null for tampered JWE", async () => {
    const jwt = "some-jwt";
    const encrypted = await encryptSession(jwt);
    const tampered = encrypted.slice(0, -5) + "XXXXX";
    const result = await decryptSession(tampered);
    expect(result).toBeNull();
  });

  it("returns null for garbage input", async () => {
    const result = await decryptSession("not-a-valid-jwe-at-all");
    expect(result).toBeNull();
  });

  it("throws when SESSION_SECRET is missing", async () => {
    vi.stubEnv("SESSION_SECRET", "");
    await expect(encryptSession("jwt")).rejects.toThrow("SESSION_SECRET");
    vi.stubEnv("SESSION_SECRET", TEST_SECRET);
  });
});
