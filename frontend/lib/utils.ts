import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { format, formatDistanceToNow, parseISO } from "date-fns";

// The standard shadcn/ui cn helper — merges class names and resolves Tailwind conflicts.
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// ---------------------------------------------------------------------------
// Date formatting — consistent across the entire app.
// All dates from the API are ISO strings; never display raw ISO strings in UI.
// ---------------------------------------------------------------------------

export function formatDate(isoString: string | null | undefined): string {
  if (!isoString) return "—";
  try {
    return format(parseISO(isoString), "d MMM yyyy");
  } catch {
    return "—";
  }
}

export function formatDateTime(isoString: string | null | undefined): string {
  if (!isoString) return "—";
  try {
    return format(parseISO(isoString), "d MMM yyyy, h:mm a");
  } catch {
    return "—";
  }
}

export function formatRelative(isoString: string | null | undefined): string {
  if (!isoString) return "—";
  try {
    return formatDistanceToNow(parseISO(isoString), { addSuffix: true });
  } catch {
    return "—";
  }
}

// ---------------------------------------------------------------------------
// Extract a human-readable error message from API responses.
// The backend returns either { detail: string } or { detail: [{msg, type}] }
// ---------------------------------------------------------------------------

export function extractApiError(error: unknown): string {
  if (!error) return "An unexpected error occurred.";
  if (typeof error === "string") return error;

  const err = error as Record<string, unknown>;

  if (err.detail) {
    if (typeof err.detail === "string") return err.detail;
    if (Array.isArray(err.detail)) {
      return err.detail
        .map((d: { msg?: string }) => d.msg ?? JSON.stringify(d))
        .join("; ");
    }
  }

  if (err.message && typeof err.message === "string") return err.message;

  return "An unexpected error occurred.";
}

// ---------------------------------------------------------------------------
// Role helpers — used everywhere for conditional rendering.
// ---------------------------------------------------------------------------

export type UserRole = "super_admin" | "league_admin" | "club_admin" | "player";

export function isAdminRole(role: UserRole | undefined): boolean {
  return role === "super_admin" || role === "league_admin" || role === "club_admin";
}

export function isLeagueLevel(role: UserRole | undefined): boolean {
  return role === "super_admin" || role === "league_admin";
}

export function isSuperAdmin(role: UserRole | undefined): boolean {
  return role === "super_admin";
}
