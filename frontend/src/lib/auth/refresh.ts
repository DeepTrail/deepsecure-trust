const REFRESH_THRESHOLD_SECONDS = 5 * 60; // 5 minutes before expiry

/**
 * Checks if a JWT is within the refresh threshold by decoding the
 * payload (base64, no verification needed — the backend signed it).
 */
export function isTokenNearExpiry(jwt: string): boolean {
  try {
    const parts = jwt.split(".");
    if (parts.length !== 3) return false;
    const payload = JSON.parse(atob(parts[1]));
    const exp = payload.exp;
    if (typeof exp !== "number") return false;
    const secondsRemaining = exp - Math.floor(Date.now() / 1000);
    return secondsRemaining > 0 && secondsRemaining < REFRESH_THRESHOLD_SECONDS;
  } catch {
    return false;
  }
}

/**
 * Calls the backend refresh endpoint. Returns the new JWT on success, null on failure.
 */
export async function refreshToken(currentJwt: string): Promise<string | null> {
  const controlUrl =
    process.env.DEEPTRAIL_CONTROL_INTERNAL_URL || "http://localhost:8000";

  try {
    const response = await fetch(`${controlUrl}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { Authorization: `Bearer ${currentJwt}` },
    });

    if (!response.ok) return null;
    const data = await response.json();
    return typeof data.token === "string" ? data.token : null;
  } catch {
    return null;
  }
}
