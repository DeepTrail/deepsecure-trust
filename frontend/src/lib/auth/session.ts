import { cookies } from "next/headers";
import { encryptSession, decryptSession } from "./cookie";

const COOKIE_NAME = "__session";
const COOKIE_MAX_AGE = 8 * 60 * 60; // 8 hours

export async function setSessionCookie(jwt: string): Promise<void> {
  const encrypted = await encryptSession(jwt);
  const cookieStore = await cookies();
  cookieStore.set(COOKIE_NAME, encrypted, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: COOKIE_MAX_AGE,
  });
}

export async function getSessionJWT(): Promise<string | null> {
  const cookieStore = await cookies();
  const cookie = cookieStore.get(COOKIE_NAME);
  if (!cookie?.value) return null;
  return decryptSession(cookie.value);
}

export async function clearSessionCookie(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.delete(COOKIE_NAME);
}
