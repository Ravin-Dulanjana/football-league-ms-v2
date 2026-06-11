// ---------------------------------------------------------------------------
// POST /api/auth/complete-challenge
//
// Called by the login form when Cognito returns NEW_PASSWORD_REQUIRED.
// Forwards { email, new_password, session } to FastAPI, then sets the
// httpOnly auth cookies exactly like /api/auth/login does on success.
// ---------------------------------------------------------------------------

import { type NextRequest, NextResponse } from "next/server";
import {
  buildIdTokenCookie,
  buildRefreshTokenCookie,
} from "@/lib/auth";

const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export async function POST(req: NextRequest): Promise<NextResponse> {
  const body = await req.json();

  const upstream = await fetch(`${API_BASE}/auth/complete-challenge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!upstream.ok) {
    const error = await upstream.json().catch(() => ({
      detail: "Failed to set new password",
    }));
    return NextResponse.json(error, { status: upstream.status });
  }

  const tokens = await upstream.json();

  // Password change succeeded — set httpOnly cookies and let the client redirect
  const res = NextResponse.json({ ok: true });
  res.headers.append("Set-Cookie", buildIdTokenCookie(tokens.id_token));
  if (tokens.refresh_token) {
    res.headers.append("Set-Cookie", buildRefreshTokenCookie(tokens.refresh_token));
  }

  return res;
}
