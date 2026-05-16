import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

export async function POST(request: NextRequest) {
  const cookieStore = await cookies();
  cookieStore.delete("__session");
  cookieStore.delete("__csrf");

  const origin = process.env.FRONTEND_ORIGIN || request.nextUrl.origin;
  return NextResponse.redirect(new URL("/login", origin));
}
