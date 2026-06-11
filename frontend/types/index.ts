// ---------------------------------------------------------------------------
// Types that mirror every backend Pydantic schema exactly.
// Keep these in sync with app/schemas/ in the FastAPI backend.
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export interface TokenResponse {
  access_token: string;
  id_token: string;
  refresh_token: string | null;
  expires_in: number;
  token_type: string;
}

// ---------------------------------------------------------------------------
// User
// ---------------------------------------------------------------------------

export type UserRole =
  | "super_admin"
  | "league_admin"
  | "club_admin"
  | "club_staff"
  | "player";

export type MemberType = "player" | "club_staff" | "user";

export interface GovernanceRoleRead {
  role: string;
  club_id: number | null;
  assigned_at: string;
}

export interface UserRead {
  id: number;
  email: string;
  role: UserRole;
  member_type: MemberType | null;
  club_id: number | null;
  player_id: number | null;
  is_active: boolean;
  is_deleted: boolean;
  force_password_change: boolean;
  created_at: string; // ISO datetime string from JSON
  last_login_at: string | null;
  // All active governance roles (can hold club_admin + league_admin simultaneously)
  governance_roles: GovernanceRoleRead[];
}

export interface UserCreate {
  email: string;
  role: UserRole;
  member_type?: MemberType;
  club_id?: number;
  temporary_password: string;
  // Player profile — required when role=player, ignored otherwise.
  full_name?: string;
  date_of_birth?: string;
  nic_number?: string;
}

export interface AssignRoleRequest {
  new_role: string;
  club_id?: number | null;
  reason: string;
}

export type AccountAction =
  | "activate"
  | "deactivate"
  | "soft_delete"
  | "reset_password"
  | "update_mobile";

export interface AccountActionRequest {
  action: AccountAction;
  reason: string;
  new_value?: string;
}

// ---------------------------------------------------------------------------
// Club
// ---------------------------------------------------------------------------

export type ClubStatus = "active" | "inactive" | "suspended";

export interface ClubRead {
  id: number;
  name: string;
  short_name: string | null;
  code: string;
  email: string | null;
  phone_number: string | null;
  logo_key: string | null;
  logo_url: string | null;
  status: ClubStatus;
  established_year: number | null;
  president_name: string | null;
  secretary_name: string | null;
  treasurer_name: string | null;
  created_at: string;
}

export interface ClubCreate {
  name: string;
  short_name?: string;
  code: string;
  email?: string;
  phone_number?: string;
  established_year?: number;
  president_name?: string;
  secretary_name?: string;
  treasurer_name?: string;
  logo_key?: string;
}

export interface ClubUpdate {
  name?: string;
  short_name?: string;
  code?: string;
  email?: string;
  phone_number?: string;
  logo_key?: string;
  status?: ClubStatus;
  established_year?: number | null;
  president_name?: string | null;
  secretary_name?: string | null;
  treasurer_name?: string | null;
}

// ---------------------------------------------------------------------------
// League Info
// ---------------------------------------------------------------------------

export interface LeagueInfoRead {
  id: number;
  league_name: string;
  founded_year: number | null;
  president_name: string | null;
  secretary_name: string | null;
  treasurer_name: string | null;
  email: string | null;
  phone_number: string | null;
  logo_key: string | null;
  logo_url: string | null;
  updated_at: string;
}

export interface LeagueInfoUpdate {
  league_name?: string;
  founded_year?: number | null;
  president_name?: string | null;
  secretary_name?: string | null;
  treasurer_name?: string | null;
  email?: string | null;
  phone_number?: string | null;
  logo_key?: string | null;
}

export interface UploadUrlResponse {
  url: string;
  fields: Record<string, string>;
  key: string;
  expires_in: number;
}

// ---------------------------------------------------------------------------
// Player
// ---------------------------------------------------------------------------

export type PlayerStatus = "pending_claim" | "active" | "inactive";

export interface PlayerRead {
  id: number;
  league_player_code: string;
  full_name: string;
  date_of_birth: string; // ISO date string "YYYY-MM-DD"
  nic_number: string;
  photo_key: string | null;
  photo_url: string | null;
  status: PlayerStatus;
  created_at: string;
  updated_at: string;
}

export interface PlayerCreate {
  full_name: string;
  date_of_birth: string;
  nic_number: string;
  photo_key?: string;
}

export interface PlayerUpdate {
  full_name?: string;
  photo_key?: string;
  status?: PlayerStatus;
}

// ---------------------------------------------------------------------------
// Season
// ---------------------------------------------------------------------------

export type SeasonStatus = "draft" | "open" | "closed" | "archived";

export interface SeasonRead {
  id: number;
  name: string;
  year: number;
  registration_open_at: string;
  registration_close_at: string;
  is_locked: boolean;
  status: SeasonStatus;
  created_at: string;
}

export interface SeasonCreate {
  name: string;
  year: number;
  registration_open_at: string;
  registration_close_at: string;
}

export interface SeasonUpdate {
  name?: string;
  registration_open_at?: string;
  registration_close_at?: string;
  is_locked?: boolean;
  status?: SeasonStatus;
}

// ---------------------------------------------------------------------------
// Registration
// ---------------------------------------------------------------------------

export type RegistrationRequestStatus =
  | "pending_player_confirmation"
  | "accepted"
  | "rejected"
  | "cancelled";

export type RegistrationStatus = "active" | "released" | "transferred";
export type RegistrationType = "new" | "transfer";

export interface RegistrationRequestRead {
  id: number;
  season_id: number;
  club_id: number;
  player_id: number;
  status: RegistrationRequestStatus;
  responded_at: string | null;
  created_at: string;
}

export interface RegistrationRequestCreate {
  player_id: number;
  club_id: number;
  season_id: number;
}

export interface PlayerSeasonRegistrationRead {
  id: number;
  season_id: number;
  club_id: number;
  player_id: number;
  registration_type: RegistrationType;
  status: RegistrationStatus;
  registered_at: string;
  released_at: string | null;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Release
// ---------------------------------------------------------------------------

export type ReleaseStatus =
  | "pending_player_confirmation"
  | "confirmed"
  | "rejected";

export interface ReleaseDocumentRead {
  id: number;
  release_id: number;
  s3_key: string;
  file_name: string;
  file_url: string;
  created_at: string;
}

export interface ReleaseRead {
  id: number;
  registration_id: number;
  player_id: number;
  from_club_id: number;
  status: ReleaseStatus;
  effective_date: string | null;
  confirmed_at: string | null;
  created_at: string;
  documents: ReleaseDocumentRead[];
}

export interface ReleaseCreate {
  registration_id: number;
  s3_key: string;
  file_name: string;
  effective_date?: string;
}

// ---------------------------------------------------------------------------
// Club Season Profile
// ---------------------------------------------------------------------------

export type ClubSeasonProfileStatus =
  | "draft"
  | "submitted"
  | "resubmitted"
  | "reviewed"
  | "approved"
  | "returned";

export interface ClubSeasonProfileRead {
  id: number;
  club_id: number;
  season_id: number;
  status: ClubSeasonProfileStatus;
  submitted_at: string | null;
  reviewed_at: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ClubSeasonProfileCreate {
  club_id: number;
  season_id: number;
}

export interface ClubSeasonProfileTransition {
  target_status: "reviewed" | "approved" | "returned";
  comment?: string;
  is_internal?: boolean;
}

export interface CommentRead {
  id: number;
  profile_id: number;
  author_id: number | null;
  content: string;
  is_internal: boolean;
  created_at: string;
}

export interface CommentCreate {
  content: string;
  is_internal?: boolean;
}

// ---------------------------------------------------------------------------
// Club Staff
// ---------------------------------------------------------------------------

export interface ClubStaffRead {
  id: number;
  club_id: number;
  season_id: number;
  full_name: string;
  role: string;
  created_at: string;
}

export interface ClubStaffCreate {
  club_id: number;
  season_id: number;
  full_name: string;
  role: string;
}

// ---------------------------------------------------------------------------
// Club Unlock Request
// ---------------------------------------------------------------------------

export type UnlockRequestStatus = "pending" | "approved" | "rejected";

export interface UnlockRequestRead {
  id: number;
  club_id: number;
  season_id: number;
  reason: string;
  status: UnlockRequestStatus;
  approval_count: number;
  created_at: string;
  decided_at: string | null;
}

export interface UnlockRequestCreate {
  club_id: number;
  season_id: number;
  reason: string;
}

// ---------------------------------------------------------------------------
// Notification
// ---------------------------------------------------------------------------

export interface NotificationRead {
  id: number;
  event_type: string;
  message: string;
  is_read: boolean;
  created_at: string;
  read_at: string | null;
}

export interface NotificationPreferenceRead {
  event_type: string;
  email_enabled: boolean;
  in_app_enabled: boolean;
}

export interface NotificationPreferenceUpdate {
  email_enabled: boolean;
  in_app_enabled: boolean;
}

// ---------------------------------------------------------------------------
// Audit Log
// ---------------------------------------------------------------------------

export interface AuditLogRead {
  id: number;
  actor_id: number | null;
  action: string;
  entity_type: string;
  entity_id: number | null;
  details: string | null;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------------------

export interface AnalyticsSummary {
  total_clubs: number;
  active_players: number;
  pending_registration_requests: number;
  pending_releases: number;
  by_club?: ClubAnalytics[];
}

export interface ClubAnalytics {
  club_id: number;
  club_name: string;
  active_players: number;
  profile_status: ClubSeasonProfileStatus | null;
  pending_registrations: number;
  pending_releases: number;
}

// ---------------------------------------------------------------------------
// API error shape
// ---------------------------------------------------------------------------

export interface ApiError {
  detail: string | { msg: string; type: string }[];
}
