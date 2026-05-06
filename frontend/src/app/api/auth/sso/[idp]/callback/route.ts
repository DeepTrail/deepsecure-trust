import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { setSessionCookie } from "@/lib/auth/session";
import { generateCsrfToken } from "@/lib/auth/csrf";

const COOKIE_MAX_AGE = 8 * 60 * 60; // 8 hours

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ idp: string }> }
) {
  const { idp } = await params;
  const searchParams = request.nextUrl.searchParams;
  const code = searchParams.get("code");
  const state = searchParams.get("state");
  const error = searchParams.get("error");

  const origin =
    process.env.FRONTEND_ORIGIN || "http://localhost:3000";

  if (error) {
    const desc = searchParams.get("error_description") || error;
    return NextResponse.redirect(
      new URL(`/login?error=${encodeURIComponent(desc)}`, origin)
    );
  }

  if (!code) {
    return NextResponse.redirect(
      new URL("/login?error=missing_code", origin)
    );
  }

  const controlUrl =
    process.env.DEEPTRAIL_CONTROL_INTERNAL_URL || "http://localhost:8000";

  const callbackUrl = new URL(
    `/api/v1/auth/sso/${idp}/callback`,
    controlUrl
  );
  callbackUrl.searchParams.set("code", code);
  if (state) callbackUrl.searchParams.set("state", state);

  try {
    const response = await fetch(callbackUrl.toString());

    if (!response.ok) {
      const body = await response.text();
      const msg = tryExtractMessage(body) || "sso_callback_failed";
      return NextResponse.redirect(
        new URL(`/login?error=${encodeURIComponent(msg)}`, origin)
      );
    }

    const data = await response.json();
    const token: string | undefined = data.token;
    if (!token) {
      return NextResponse.redirect(
        new URL("/login?error=no_token", origin)
      );
    }

    await setSessionCookie(token);

    const csrfToken = generateCsrfToken();
    const cookieStore = await cookies();
    cookieStore.set("__csrf", csrfToken, {
      httpOnly: false,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: COOKIE_MAX_AGE,
    });

    return NextResponse.redirect(new URL("/dashboard", origin));
  } catch {
    return NextResponse.redirect(
      new URL(`/login?error=sso_unavailable&idp=${idp}`, origin)
    );
  }
}

function tryExtractMessage(body: string): string | null {
  try {
    const parsed = JSON.parse(body);
    return parsed.detail || parsed.message || parsed.error || null;
  } catch {
    return null;
  }
}
