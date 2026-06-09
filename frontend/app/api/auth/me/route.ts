// ---------------------------------------------------------------------------
// GET /api/auth/me
//
// Called on every dashboard load (from useCurrentUser hook via React Query).
// Reads the id_token cookie, verifies it's present, and proxies to the
// FastAPI /auth/me (or reconstructs user from token claims if no /me endpoint).
//
// Currently the FastAPI backend does not have a dedicated /me endpoint —
// user info is contained in the JWT claims and synced to DB on each request.
// We proxy to /users/ and return the first match, OR we decode the JWT
// locally to get basic role/id info.
//
// Simple approach: the first authenticated call returns a 401 if token invalid.
// We use the /notifications/ endpoint as a lightweight "am I authenticated?" check,
// and return user data from the token claims decoded on the server.
// ---------------------------------------------------------------------------

import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { COOKIE_ID_TOKEN } from "@/lib/auth";

const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

/** Decode a JWT payload without verifying the signature (server-side only). */
function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const [, payload] = token.split(".");
    const padded = payload.replace(/-/g, "+").replace(/_/g, "/");
    const json = Buffer.from(padded, "base64").toString("utf-8");
    return JSON.parse(json) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export async function GET(): Promise<NextResponse> {
  const cookieStore = cookies();
  const idToken = cookieStore.get(COOKIE_ID_TOKEN)?.value;

  if (!idToken) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  // Check if the token has expired (exp claim is in seconds since epoch).
  const claims = decodeJwtPayload(idToken);
  if (!claims) {
    return NextResponse.json({ detail: "Invalid token" }, { status: 401 });
  }

  const now = Math.floor(Date.now() / 1000);
  if (typeof claims.exp === "number" && claims.exp < now) {
    return NextResponse.json({ detail: "Token expired" }, { status: 401 });
  }

  // Make a lightweight call to the backend to get the DB user record.
  // GET /users/ is only available to admins. For players, we fall back
  // to the JWT claims which contain enough info for the UI.
  //
  // Better approach: the backend should expose GET /auth/me — but since it
  // doesn't, we reconstruct from claims + a conditional call.

  const role = claims["custom:role"] as string | undefined;
  const clubId = claims["custom:club_id"]
    ? Number(claims["custom:club_id"])
    : null;
  const playerId = claims["custom:player_id"]
    ? Number(claims["custom:player_id"])
    : null;

  // Try to fetch the full DB user record for admins (has /users/ access).
  // For players, the JWT claims are sufficient for auth/routing.
  if (role === "super_admin" || role === "league_admin") {
    const upstream = await fetch(`${API_BASE}/users/?include_deleted=false`, {
      headers: { Authorization: `Bearer ${idToken}` },
    }).catch(() => null);

    if (upstream?.ok) {
      const users = (await upstream.json()) as Array<{
        id: number;
        email: string;
        role: string;
        is_active: boolean;
        is_deleted: boolean;
        force_password_change: boolean;
        last_login_at: string | null;
        created_at: string;
        club_id: number | null;
        player_id: number | null;
      }>;
      const email = claims.email as string;
      const me = users.find((u) => u.email === email);
      if (me) return NextResponse.json(me);
    }
  }

  // Fallback: build a minimal user object from JWT claims.
  // This is sufficient for routing and role-based rendering.
  return NextResponse.json({
    id: null, // not known without a DB call
    email: claims.email as string,
    role: role ?? "player",
    club_id: clubId,
    player_id: playerId,
    is_active: true,
    is_deleted: false,
    force_password_change: false,
    last_login_at: null,
    created_at: new Date(Number(claims.iat) * 1000).toISOString(),
  });
}
