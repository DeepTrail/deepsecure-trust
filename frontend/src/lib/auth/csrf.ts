import { type NextRequest } from "next/server";

export function validateCsrf(request: NextRequest): boolean {
  const headerToken = request.headers.get("X-CSRF-Token");
  const cookieToken = request.cookies.get("__csrf")?.value;
  if (!headerToken || !cookieToken) return false;
  return headerToken === cookieToken;
}

export function generateCsrfToken(): string {
  return crypto.randomUUID();
}
