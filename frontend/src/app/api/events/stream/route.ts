import { NextResponse } from "next/server";
import { getSessionJWT, setSessionCookie } from "@/lib/auth/session";
import { isTokenNearExpiry, refreshToken } from "@/lib/auth/refresh";

const CONTROL_URL =
  process.env.DEEPTRAIL_CONTROL_INTERNAL_URL || "http://localhost:8000";

const UPSTREAM_PATH = "/api/v1/audit/events/stream";

export async function GET() {
  let jwt = await getSessionJWT();
  if (!jwt) {
    return NextResponse.json(
      { error: "Unauthorized", message: "No active session" },
      { status: 401 }
    );
  }

  if (isTokenNearExpiry(jwt)) {
    try {
      const newToken = await refreshToken(jwt);
      if (newToken) {
        await setSessionCookie(newToken);
        jwt = newToken;
      }
    } catch {
      // proceed with current token if refresh fails
    }
  }

  try {
    const upstream = await fetch(`${CONTROL_URL}${UPSTREAM_PATH}`, {
      headers: {
        Authorization: `Bearer ${jwt}`,
        Accept: "text/event-stream",
      },
      // @ts-expect-error -- Node fetch supports duplex for streaming
      duplex: "half",
    });

    if (!upstream.ok) {
      return NextResponse.json(
        {
          error: "Bad Gateway",
          message: `Upstream returned ${upstream.status}`,
        },
        { status: upstream.status >= 500 ? 502 : upstream.status }
      );
    }

    if (!upstream.body) {
      return NextResponse.json(
        { error: "Bad Gateway", message: "No response body from upstream" },
        { status: 502 }
      );
    }

    const stream = new ReadableStream({
      async start(controller) {
        const reader = upstream.body!.getReader();
        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            controller.enqueue(value);
          }
          controller.close();
        } catch {
          controller.close();
        }
      },
      cancel() {
        upstream.body?.cancel();
      },
    });

    return new Response(stream, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "SSE upstream request failed";
    return NextResponse.json(
      { error: "Bad Gateway", message },
      { status: 502 }
    );
  }
}
