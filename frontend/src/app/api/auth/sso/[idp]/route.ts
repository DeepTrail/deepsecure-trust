import { NextRequest, NextResponse } from "next/server";

const VALID_IDPS = new Set(["keycloak", "google", "okta", "entra"]);

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ idp: string }> }
) {
  const { idp } = await params;

  if (!VALID_IDPS.has(idp)) {
    return NextResponse.json(
      { error: "Bad Request", message: `Unsupported identity provider: ${idp}` },
      { status: 400 }
    );
  }

  const controlUrl =
    process.env.DEEPTRAIL_CONTROL_INTERNAL_URL || "http://localhost:8000";

  const frontendOrigin =
    process.env.FRONTEND_ORIGIN || "http://localhost:3000";
  const callbackUrl = new URL(`/api/auth/sso/${idp}/callback`, frontendOrigin);

  const authorizeUrl = new URL(
    `/api/v1/auth/sso/${idp}/authorize`,
    controlUrl
  );
  authorizeUrl.searchParams.set("response_mode", "redirect");
  authorizeUrl.searchParams.set("redirect_uri", callbackUrl.toString());

  try {
    const response = await fetch(authorizeUrl.toString(), { redirect: "manual" });

    if (response.status >= 300 && response.status < 400) {
      const location = response.headers.get("Location");
      if (location) {
        return NextResponse.redirect(location);
      }
    }

    if (response.ok) {
      const data = await response.json();
      if (data.authorization_url) {
        return NextResponse.redirect(data.authorization_url);
      }
    }

    return NextResponse.redirect(
      new URL(`/login?error=sso_failed&idp=${idp}`, frontendOrigin)
    );
  } catch {
    return NextResponse.redirect(
      new URL(`/login?error=sso_unavailable&idp=${idp}`, frontendOrigin)
    );
  }
}
