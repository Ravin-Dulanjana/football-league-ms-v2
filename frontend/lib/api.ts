// ---------------------------------------------------------------------------
// lib/api.ts — typed fetch wrapper for all backend calls.
//
// Two modes:
//   1. CLIENT-SIDE: calls go to /api/** (our Next.js route handlers).
//      The route handler reads the httpOnly cookie, injects the Bearer token,
//      and proxies to the FastAPI backend. The token never touches client JS.
//
//   2. SERVER-SIDE (route handlers): calls go directly to API_BASE_URL,
//      with the token read from cookies and injected here.
//
// All functions return typed results. Errors throw an Error with the
// backend's detail message already extracted.
// ---------------------------------------------------------------------------

import type {
  AccountActionRequest,
  AnalyticsSummary,
  AssignRoleRequest,
  AuditLogRead,
  ClubCreate,
  ClubRead,
  ClubSeasonProfileCreate,
  ClubSeasonProfileRead,
  ClubSeasonProfileTransition,
  ClubStaffCreate,
  ClubStaffRead,
  ClubUpdate,
  CommentCreate,
  CommentRead,
  LeagueInfoRead,
  LeagueInfoUpdate,
  NotificationPreferenceRead,
  NotificationPreferenceUpdate,
  NotificationRead,
  PlayerCreate,
  PlayerRead,
  PlayerSeasonRegistrationRead,
  PlayerUpdate,
  RegistrationRequestCreate,
  RegistrationRequestRead,
  ReleaseCreate,
  ReleaseRead,
  SeasonCreate,
  SeasonRead,
  SeasonUpdate,
  UnlockRequestCreate,
  UnlockRequestRead,
  UploadUrlResponse,
  UserCreate,
  UserRead,
} from "@/types";

// ---------------------------------------------------------------------------
// Core fetch wrapper
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  // Client-side: route through /api proxy so token stays in httpOnly cookie.
  // Server-side (route handlers): use API_BASE_URL directly (set as env var).
  const base =
    typeof window === "undefined"
      ? (process.env.API_BASE_URL ?? "http://localhost:8000")
      : ""; // empty = relative URL, hits /api/* on the same origin

  const url = typeof window === "undefined"
    ? `${base}${path}` // server-side: direct to backend
    : `/api/proxy?path=${encodeURIComponent(path)}`; // client-side: via proxy

  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
  });

  if (!res.ok) {
    let detail = `Request failed: ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else if (Array.isArray(body?.detail)) {
        detail = body.detail.map((d: { msg: string }) => d.msg).join("; ");
      }
    } catch {
      // non-JSON error body
    }
    throw new ApiError(detail, res.status);
  }

  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}

// Client-side: all calls go to /api/proxy which handles the token injection.
// Server-side (route handlers): direct fetch with token from cookies.
// We export a helper for route handlers to call the backend with a token.

export async function serverFetch<T>(
  path: string,
  token: string,
  options: RequestInit = {}
): Promise<T> {
  const base = process.env.API_BASE_URL ?? "http://localhost:8000";
  const res = await fetch(`${base}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(options.headers ?? {}),
    },
  });

  if (!res.ok) {
    let detail = `Request failed: ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // non-JSON
    }
    throw new ApiError(detail, res.status);
  }

  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

// Auth endpoints are called via client-side /api/auth/* route handlers,
// so they don't go through /api/proxy.

export const authApi = {
  login: (email: string, password: string) =>
    fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }),

  logout: () =>
    fetch("/api/auth/logout", { method: "POST" }),

  me: () =>
    fetch("/api/auth/me").then(async (res) => {
      if (!res.ok) throw new ApiError("Unauthorized", res.status);
      return res.json() as Promise<UserRead>;
    }),
};

// ---------------------------------------------------------------------------
// Clubs
// ---------------------------------------------------------------------------

export const clubsApi = {
  list: () => apiFetch<ClubRead[]>("/clubs/"),
  get: (id: number) => apiFetch<ClubRead>(`/clubs/${id}/`),
  create: (data: ClubCreate) =>
    apiFetch<ClubRead>("/clubs/", { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: ClubUpdate) =>
    apiFetch<ClubRead>(`/clubs/${id}/`, { method: "PATCH", body: JSON.stringify(data) }),
  logoUploadUrl: (clubId: number, filename: string, contentType = "image/jpeg") =>
    apiFetch<UploadUrlResponse>(
      `/clubs/${clubId}/logo-upload-url/?filename=${encodeURIComponent(filename)}&content_type=${encodeURIComponent(contentType)}`
    ),
};

// ---------------------------------------------------------------------------
// Players
// ---------------------------------------------------------------------------

export const playersApi = {
  list: () => apiFetch<PlayerRead[]>("/players/"),
  get: (id: number) => apiFetch<PlayerRead>(`/players/${id}/`),
  create: (data: PlayerCreate) =>
    apiFetch<PlayerRead>("/players/", { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: PlayerUpdate) =>
    apiFetch<PlayerRead>(`/players/${id}/`, { method: "PATCH", body: JSON.stringify(data) }),
  photoUploadUrl: (playerId: number, filename: string, contentType = "image/jpeg") =>
    apiFetch<UploadUrlResponse>(
      `/players/${playerId}/photo-upload-url/?filename=${encodeURIComponent(filename)}&content_type=${encodeURIComponent(contentType)}`
    ),
};

// ---------------------------------------------------------------------------
// Seasons
// ---------------------------------------------------------------------------

export const seasonsApi = {
  list: () => apiFetch<SeasonRead[]>("/seasons/"),
  get: (id: number) => apiFetch<SeasonRead>(`/seasons/${id}/`),
  create: (data: SeasonCreate) =>
    apiFetch<SeasonRead>("/seasons/", { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: SeasonUpdate) =>
    apiFetch<SeasonRead>(`/seasons/${id}/`, { method: "PATCH", body: JSON.stringify(data) }),
};

// ---------------------------------------------------------------------------
// Registration Requests
// ---------------------------------------------------------------------------

export const registrationsApi = {
  list: () => apiFetch<RegistrationRequestRead[]>("/registration-requests/"),
  create: (data: RegistrationRequestCreate) =>
    apiFetch<RegistrationRequestRead>("/registration-requests/", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  decide: (id: number, decision: "accept") =>
    apiFetch<RegistrationRequestRead>(`/registration-requests/${id}/decide/`, {
      method: "POST",
      body: JSON.stringify({ decision }),
    }),
  listPlayerSeasonRegistrations: (params?: { club_id?: number; season_id?: number }) => {
    const q = new URLSearchParams();
    if (params?.club_id) q.set("club_id", String(params.club_id));
    if (params?.season_id) q.set("season_id", String(params.season_id));
    return apiFetch<PlayerSeasonRegistrationRead[]>(
      `/registration-requests/player-season-registrations/?${q}`
    );
  },
};

// ---------------------------------------------------------------------------
// Releases
// ---------------------------------------------------------------------------

export const releasesApi = {
  list: () => apiFetch<ReleaseRead[]>("/releases/"),
  create: (data: ReleaseCreate) =>
    apiFetch<ReleaseRead>("/releases/", { method: "POST", body: JSON.stringify(data) }),
  decide: (id: number, decision: "confirm") =>
    apiFetch<ReleaseRead>(`/releases/${id}/decide/`, {
      method: "POST",
      body: JSON.stringify({ decision }),
    }),
  documentUploadUrl: (filename: string, contentType = "application/pdf") =>
    apiFetch<UploadUrlResponse>(
      `/releases/document-upload-url/?filename=${encodeURIComponent(filename)}&content_type=${encodeURIComponent(contentType)}`
    ),
};

// ---------------------------------------------------------------------------
// Users
// ---------------------------------------------------------------------------

export const usersApi = {
  list: (includeDeleted = false) =>
    apiFetch<UserRead[]>(`/users/?include_deleted=${includeDeleted}`),
  get: (id: number) => apiFetch<UserRead>(`/users/${id}/`),
  create: (data: UserCreate) =>
    apiFetch<UserRead>("/users/", { method: "POST", body: JSON.stringify(data) }),
  delete: (id: number, reason: string) =>
    apiFetch<void>(`/users/${id}/`, {
      method: "DELETE",
      body: JSON.stringify({ reason }),
    }),
  accountAction: (id: number, data: AccountActionRequest) =>
    apiFetch<UserRead>(`/users/${id}/account-action/`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  hardDelete: (id: number) =>
    apiFetch<void>(`/users/${id}/hard-delete/`, { method: "DELETE" }),
  restore: (id: number) =>
    apiFetch<UserRead>(`/users/${id}/restore/`, { method: "POST" }),
  assignRole: (id: number, data: AssignRoleRequest) =>
    apiFetch<UserRead>(`/users/${id}/role/`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
};

// ---------------------------------------------------------------------------
// Club Season Profiles
// ---------------------------------------------------------------------------

export const profilesApi = {
  list: () => apiFetch<ClubSeasonProfileRead[]>("/club-season-profiles/"),
  create: (data: ClubSeasonProfileCreate) =>
    apiFetch<ClubSeasonProfileRead>("/club-season-profiles/", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  submit: (id: number) =>
    apiFetch<ClubSeasonProfileRead>(`/club-season-profiles/${id}/submit/`, { method: "POST" }),
  transition: (id: number, data: ClubSeasonProfileTransition) =>
    apiFetch<ClubSeasonProfileRead>(`/club-season-profiles/${id}/transition/`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  listComments: (profileId: number) =>
    apiFetch<CommentRead[]>(`/club-season-profiles/${profileId}/comments/`),
  addComment: (profileId: number, data: CommentCreate) =>
    apiFetch<CommentRead>(`/club-season-profiles/${profileId}/comments/`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

// ---------------------------------------------------------------------------
// Club Staff
// ---------------------------------------------------------------------------

export const staffApi = {
  list: (clubId?: number, seasonId?: number) => {
    const params = new URLSearchParams();
    if (clubId) params.set("club_id", String(clubId));
    if (seasonId) params.set("season_id", String(seasonId));
    return apiFetch<ClubStaffRead[]>(`/club-staff/?${params}`);
  },
  create: (data: ClubStaffCreate) =>
    apiFetch<ClubStaffRead>("/club-staff/", { method: "POST", body: JSON.stringify(data) }),
  delete: (id: number) =>
    apiFetch<void>(`/club-staff/${id}/`, { method: "DELETE" }),
};

// ---------------------------------------------------------------------------
// Club Unlock Requests
// ---------------------------------------------------------------------------

export const unlockRequestsApi = {
  list: () => apiFetch<UnlockRequestRead[]>("/club-unlock-requests/"),
  create: (data: UnlockRequestCreate) =>
    apiFetch<UnlockRequestRead>("/club-unlock-requests/", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  decide: (id: number, decision: "approve" | "reject") =>
    apiFetch<UnlockRequestRead>(`/club-unlock-requests/${id}/decide/`, {
      method: "POST",
      body: JSON.stringify({ decision }),
    }),
};

// ---------------------------------------------------------------------------
// Notifications
// ---------------------------------------------------------------------------

export const notificationsApi = {
  list: () => apiFetch<NotificationRead[]>("/notifications/"),
  markRead: (id: number) =>
    apiFetch<NotificationRead>(`/notifications/${id}/read/`, { method: "POST" }),
  markAllRead: () =>
    apiFetch<{ count: number }>("/notifications/mark-all-read/", { method: "POST" }),
  getPreferences: () => apiFetch<NotificationPreferenceRead[]>("/notifications/preferences/"),
  updatePreference: (eventType: string, data: NotificationPreferenceUpdate) =>
    apiFetch<NotificationPreferenceRead>(`/notifications/preferences/${eventType}/`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
};

// ---------------------------------------------------------------------------
// Audit Logs
// ---------------------------------------------------------------------------

export const auditLogsApi = {
  list: (params?: {
    action?: string;
    actor_id?: number;
    entity_type?: string;
    entity_id?: number;
    limit?: number;
    offset?: number;
  }) => {
    const q = new URLSearchParams();
    if (params?.action) q.set("action", params.action);
    if (params?.actor_id) q.set("actor_id", String(params.actor_id));
    if (params?.entity_type) q.set("entity_type", params.entity_type);
    if (params?.entity_id) q.set("entity_id", String(params.entity_id));
    if (params?.limit) q.set("limit", String(params.limit));
    if (params?.offset) q.set("offset", String(params.offset));
    return apiFetch<AuditLogRead[]>(`/audit-logs/?${q}`);
  },
  exportCsv: () => `/api/proxy?path=${encodeURIComponent("/audit-logs/export/")}`,
};

// ---------------------------------------------------------------------------
// Reports
// ---------------------------------------------------------------------------

export const reportsApi = {
  export: (reportType: string, fileFormat: string, seasonId?: number) => {
    const q = new URLSearchParams({ report_type: reportType, file_format: fileFormat });
    if (seasonId) q.set("season_id", String(seasonId));
    return `/api/proxy?path=${encodeURIComponent(`/reports/export/?${q}`)}`;
  },
  analytics: () => apiFetch<AnalyticsSummary>("/analytics/summary/"),
};

// ---------------------------------------------------------------------------
// League Info
// ---------------------------------------------------------------------------

export const leagueInfoApi = {
  get: () => apiFetch<LeagueInfoRead>("/league-info/"),
  update: (data: LeagueInfoUpdate) =>
    apiFetch<LeagueInfoRead>("/league-info/", {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  logoUploadUrl: (filename: string, contentType = "image/jpeg") =>
    apiFetch<UploadUrlResponse>(
      `/league-info/logo-upload-url/?filename=${encodeURIComponent(filename)}&content_type=${encodeURIComponent(contentType)}`
    ),
};
