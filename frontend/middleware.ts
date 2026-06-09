// ---------------------------------------------------------------------------
// middleware.ts — route protection for all dashboard pages.
//
// Next.js middleware runs at the Edge before any page component renders.
// It runs on every request that matches the `config.matcher` below.
//
// Logic:
//   - If the request is for /dashboard/** and there's no fl_id_token cookie
//     → redirect to /login
//   - If the request is for /login and there IS a fl_id_token cookie
//     → redirect to /dashboard (already logged in)
//   - /api/** requests pass through (the route handlers do their own auth)
// ---------------------------------------------------------------------------

import { type NextRequest, NextResponse } from "next/server";
import { COOKIE_ID_TOKEN } from "@/lib/auth";

export function middleware(req: NextRequest): NextResponse {
  const { pathname } = req.nextUrl;
  const token = req.cookies.get(COOKIE_ID_TOKEN)?.value;

  const isDashboard = pathname.startsWith("/dashboard");
  const isLogin = pathname === "/login" || pathname === "/";

  if (isDashboard && !token) {
    const loginUrl = new URL("/login", req.url);
    // Pass the original destination so we can redirect back after login
    loginUrl.searchParams.set("from", pathname);
    return NextResponse.redirect(loginUrl);
  }

  if (isLogin && token) {
    return NextResponse.redirect(new URL("/dashboard", req.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    // Match all dashboard routes
    "/dashboard/:path*",
    // Match login page (to redirect away if already authed)
    "/login",
    // Match root (redirect to dashboard or login)
    "/",
  ],
};
