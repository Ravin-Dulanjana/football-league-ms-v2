// ---------------------------------------------------------------------------
// /api/proxy — universal backend proxy route handler.
//
// All client-side API calls go through here. This route:
//   1. Reads the fl_id_token httpOnly cookie (never accessible to client JS)
//   2. Injects it as Authorization: Bearer <token>
//   3. Forwards the request to the FastAPI backend
//   4. Streams the response back to the client
//
// The backend URL is never exposed to the browser.
// The token is never accessible to client JS.
// ---------------------------------------------------------------------------

import { cookies } from "next/headers";
import { type NextRequest, NextResponse } from "next/server";
import { COOKIE_ID_TOKEN } from "@/lib/auth";

const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

async function handler(req: NextRequest): Promise<NextResponse> {
  const path = req.nextUrl.searchParams.get("path");
  if (!path) {
    return NextResponse.json({ detail: "Missing path parameter" }, { status: 400 });
  }

  const cookieStore = cookies();
  const token = cookieStore.get(COOKIE_ID_TOKEN)?.value;

  if (!token) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const targetUrl = `${API_BASE}${path}`;

  // Forward the original body (for POST/PATCH/PUT/DELETE)
  let body: BodyInit | null = null;
  if (req.method !== "GET" && req.method !== "HEAD") {
    body = await req.text();
  }

  const upstream = await fetch(targetUrl, {
    method: req.method,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: body || undefined,
  });

  // For CSV/text responses (audit log export, reports), stream as text.
  const contentType = upstream.headers.get("content-type") ?? "";
  if (contentType.includes("text/plain") || contentType.includes("text/csv")) {
    const text = await upstream.text();
    return new NextResponse(text, {
      status: upstream.status,
      headers: {
        "Content-Type": contentType,
        "Content-Disposition": upstream.headers.get("Content-Disposition") ?? "",
      },
    });
  }

  // JSON responses
  const data = upstream.status === 204 ? null : await upstream.json();
  return NextResponse.json(data, { status: upstream.status });
}

export const GET = handler;
export const POST = handler;
export const PATCH = handler;
export const PUT = handler;
export const DELETE = handler;
