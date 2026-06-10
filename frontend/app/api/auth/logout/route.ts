// ---------------------------------------------------------------------------
// POST /api/auth/logout
//
// Calls FastAPI /auth/logout (Cognito GlobalSignOut) with the access token,
// then clears both httpOnly cookies.
// ---------------------------------------------------------------------------

import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import {
  clearCookie,
  COOKIE_ID_TOKEN,
  COOKIE_REFRESH_TOKEN,
} from "@/lib/auth";

const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export async function POST(): Promise<NextResponse> {
  const cookieStore = cookies();
  const idToken = cookieStore.get(COOKIE_ID_TOKEN)?.value;

  // Best-effort: tell Cognito to revoke the tokens. If this fails (e.g. token
  // already expired), we still clear the cookies so the user is logged out locally.
  if (idToken) {
    await fetch(`${API_BASE}/auth/logout`, {
      method: "POST",
      headers: { Authorization: `Bearer ${idToken}` },
    }).catch(() => {
      // Swallow — Cognito logout errors don't prevent local session clearing
    });
  }

  const res = NextResponse.json({ ok: true });
  res.headers.append("Set-Cookie", clearCookie(COOKIE_ID_TOKEN));
  res.headers.append("Set-Cookie", clearCookie(COOKIE_REFRESH_TOKEN));
  return res;
}
