// ---------------------------------------------------------------------------
// Auth cookie helpers — server-side only (used in route handlers + middleware).
//
// Tokens are NEVER exposed to client JS. The httpOnly cookie is set by our
// route handler (/api/auth/login) and read only on the server.
//
// Cookie names:
//   fl_id_token      — Cognito ID token (contains role claims, used as Bearer)
//   fl_refresh_token — Cognito refresh token (used to get new ID tokens)
// ---------------------------------------------------------------------------

export const COOKIE_ID_TOKEN = "fl_id_token";
export const COOKIE_REFRESH_TOKEN = "fl_refresh_token";

// How long (seconds) the id_token cookie should live.
// Cognito default: 1 hour. We set 55 minutes so the cookie expires
// slightly before the token itself, prompting refresh before a 401.
export const ID_TOKEN_MAX_AGE = 55 * 60;

// Refresh token cookie: 30 days (Cognito default).
export const REFRESH_TOKEN_MAX_AGE = 30 * 24 * 60 * 60;

/**
 * Build the Set-Cookie header string for the id_token.
 * httpOnly: JS cannot read it.
 * SameSite=Strict: not sent on cross-site requests (CSRF protection).
 * Secure: only sent over HTTPS. Dev builds work without it (localhost).
 */
export function buildIdTokenCookie(token: string, secure: boolean = process.env.NODE_ENV === "production"): string {
  const parts = [
    `${COOKIE_ID_TOKEN}=${token}`,
    `Max-Age=${ID_TOKEN_MAX_AGE}`,
    "Path=/",
    "HttpOnly",
    "SameSite=Strict",
  ];
  if (secure) parts.push("Secure");
  return parts.join("; ");
}

export function buildRefreshTokenCookie(token: string, secure: boolean = process.env.NODE_ENV === "production"): string {
  const parts = [
    `${COOKIE_REFRESH_TOKEN}=${token}`,
    `Max-Age=${REFRESH_TOKEN_MAX_AGE}`,
    "Path=/",
    "HttpOnly",
    "SameSite=Strict",
  ];
  if (secure) parts.push("Secure");
  return parts.join("; ");
}

/** Build the Set-Cookie header that clears a cookie. */
export function clearCookie(name: string): string {
  return `${name}=; Max-Age=0; Path=/; HttpOnly; SameSite=Strict`;
}
