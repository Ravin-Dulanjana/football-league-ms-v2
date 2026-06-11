// ---------------------------------------------------------------------------
// GET /api/auth/me
//
// Called on every dashboard load (from useCurrentUser hook via React Query).
// Reads the id_token cookie, verifies it's present (and not expired), then
// proxies to GET /users/me/ on the FastAPI backend to get the full DB user
// record — including governance_roles, member_type, and the real DB id.
//
// This replaces the old approach that only called the backend for
// super_admin/league_admin and fell back to JWT claims (returning id: null)
// for every other role, which broke club-edit gating and profile pages.
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

  // Quick client-side expiry check (no network round-trip).
  const claims = decodeJwtPayload(idToken);
  if (!claims) {
    return NextResponse.json({ detail: "Invalid token" }, { status: 401 });
  }

  const now = Math.floor(Date.now() / 1000);
  if (typeof claims.exp === "number" && claims.exp < now) {
    return NextResponse.json({ detail: "Token expired" }, { status: 401 });
  }

  // Fetch the full DB user record from GET /users/me/.
  // This endpoint is accessible to ALL authenticated users and returns the
  // real DB id, governance_roles, member_type, last_login_at, etc.
  const res = await fetch(`${API_BASE}/users/me/`, {
    headers: { Authorization: `Bearer ${idToken}` },
  }).catch(() => null);

  if (res?.ok) {
    const me = await res.json();
    return NextResponse.json(me);
  }

  // If the backend is unreachable, fall back to JWT claims so the UI
  // doesn't fully break — but surface the real status code if the backend
  // returned one (e.g. 401 means the token was rejected by the backend).
  if (res && res.status === 401) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  // Generic fallback: reconstruct from claims.
  // id is null here because we couldn't reach the DB — callers must handle this.
  const role = claims["custom:role"] as string | undefined;
  const clubId = claims["custom:club_id"]
    ? Number(claims["custom:club_id"])
    : null;
  const playerId = claims["custom:player_id"]
    ? Number(claims["custom:player_id"])
    : null;

  return NextResponse.json({
    id: null,
    email: claims.email as string,
    role: role ?? "player",
    club_id: clubId,
    player_id: playerId,
    is_active: true,
    is_deleted: false,
    force_password_change: false,
    last_login_at: null,
    created_at: new Date(Number(claims.iat) * 1000).toISOString(),
    governance_roles: [],
  });
}
