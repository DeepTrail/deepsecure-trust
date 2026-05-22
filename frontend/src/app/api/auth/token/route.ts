import { NextResponse } from "next/server";
import { getSessionJWT } from "@/lib/auth/session";

export async function GET() {
  const jwt = await getSessionJWT();
  if (!jwt) {
    return NextResponse.json(
      { error: "No active session. Sign in via the UI first." },
      { status: 401 }
    );
  }

  return NextResponse.json({ token: jwt });
}
