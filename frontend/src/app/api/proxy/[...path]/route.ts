import { NextRequest, NextResponse } from "next/server";
import { getSessionJWT, setSessionCookie } from "@/lib/auth/session";
import { validateCsrf } from "@/lib/auth/csrf";
import { isTokenNearExpiry, refreshToken } from "@/lib/auth/refresh";

const MUTATING_METHODS = new Set(["POST", "PUT", "DELETE", "PATCH"]);

function getUpstreamUrl(pathSegments: string[]): string {
  const controlUrl =
    process.env.DEEPTRAIL_CONTROL_INTERNAL_URL || "http://localhost:8000";
  const gatewayUrl =
    process.env.DEEPTRAIL_GATEWAY_INTERNAL_URL || "http://localhost:8002";

  if (pathSegments[0] === "gateway") {
    const cleanPath = pathSegments.slice(1).join("/");
    return `${gatewayUrl}/api/v1/${cleanPath}`;
  }

  return `${controlUrl}/api/v1/${pathSegments.join("/")}`;
}

async function proxyHandler(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  let jwt = await getSessionJWT();
  if (!jwt) {
    return NextResponse.json(
      { error: "Unauthorized", message: "No active session" },
      { status: 401 }
    );
  }

  if (isTokenNearExpiry(jwt)) {
    const newToken = await refreshToken(jwt);
    if (newToken) {
      jwt = newToken;
      await setSessionCookie(newToken);
    }
  }

  if (MUTATING_METHODS.has(request.method)) {
    if (!validateCsrf(request)) {
      return NextResponse.json(
        { error: "Forbidden", message: "Invalid CSRF token" },
        { status: 403 }
      );
    }
  }

  const { path } = await params;
  const upstream = getUpstreamUrl(path);

  const headers = new Headers();
  headers.set("Authorization", `Bearer ${jwt}`);
  headers.set(
    "Content-Type",
    request.headers.get("Content-Type") || "application/json"
  );
  headers.set("Accept", request.headers.get("Accept") || "application/json");

  const hasBody = !["GET", "HEAD"].includes(request.method);
  let body: ArrayBuffer | undefined;
  if (hasBody) {
    try {
      body = await request.arrayBuffer();
    } catch {
      body = undefined;
    }
  }

  try {
    const upstream_response = await fetch(upstream, {
      method: request.method,
      headers,
      body: hasBody ? body : undefined,
    });

    const responseBody = await upstream_response.arrayBuffer();
    const responseHeaders = new Headers();
    const contentType = upstream_response.headers.get("Content-Type");
    if (contentType) responseHeaders.set("Content-Type", contentType);

    return new NextResponse(responseBody, {
      status: upstream_response.status,
      statusText: upstream_response.statusText,
      headers: responseHeaders,
    });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Upstream request failed";
    return NextResponse.json(
      { error: "Bad Gateway", message },
      { status: 502 }
    );
  }
}

export {
  proxyHandler as GET,
  proxyHandler as POST,
  proxyHandler as PUT,
  proxyHandler as DELETE,
  proxyHandler as PATCH,
};
