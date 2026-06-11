// ---------------------------------------------------------------------------
// POST /api/auth/login
//
// Flow:
//   1. Receive { email, password } from the login form
//   2. POST to FastAPI /auth/login
//   3. On success: set httpOnly cookies for id_token and refresh_token
//   4. Return { ok: true } to the client — never the token itself
//
// The client JS never sees the token. The cookie is set server-side only.
// ---------------------------------------------------------------------------

import { type NextRequest, NextResponse } from "next/server";
import {
  buildIdTokenCookie,
  buildRefreshTokenCookie,
} from "@/lib/auth";

const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export async function POST(req: NextRequest): Promise<NextResponse> {
  const credentials = await req.json();

  const upstream = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(credentials),
  });

  if (!upstream.ok) {
    const error = await upstream.json().catch(() => ({ detail: "Login failed" }));
    return NextResponse.json(error, { status: upstream.status });
  }

  const body = await upstream.json();

  // Cognito NEW_PASSWORD_REQUIRED — pass the challenge info to the client so
  // the login form can show the "Set new password" step. No cookies are set yet.
  if (body?.challenge === "NEW_PASSWORD_REQUIRED") {
    return NextResponse.json(body);
  }

  // Normal success — set httpOnly cookies. JS on the page can NEVER read these.
  const res = NextResponse.json({ ok: true });

  res.headers.append("Set-Cookie", buildIdTokenCookie(body.id_token));
  if (body.refresh_token) {
    res.headers.append("Set-Cookie", buildRefreshTokenCookie(body.refresh_token));
  }

  return res;
}
