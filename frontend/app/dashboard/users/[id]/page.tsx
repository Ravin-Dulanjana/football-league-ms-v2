"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Building2, Calendar, Mail, Shield, User } from "lucide-react";

import { StatusBadge } from "@/components/shared/StatusBadge";
import { usersApi, playersApi, clubsApi } from "@/lib/api";
import { formatDate, formatRelative } from "@/lib/utils";
import type { ClubRead, PlayerRead, UserRead } from "@/types";

export default function UserDetailPage() {
  const params = useParams();
  const router = useRouter();
  const userId = Number(params.id);

  const { data: user, isLoading } = useQuery<UserRead>({
    queryKey: ["user", userId],
    queryFn: () => usersApi.get(userId),
  });

  const { data: player } = useQuery<PlayerRead>({
    queryKey: ["player", user?.player_id],
    queryFn: () => playersApi.get(user!.player_id!),
    enabled: !!user?.player_id,
  });

  const { data: club } = useQuery<ClubRead>({
    queryKey: ["club", user?.club_id],
    queryFn: () => clubsApi.get(user!.club_id!),
    enabled: !!user?.club_id,
  });

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <div className="h-8 bg-muted rounded animate-pulse w-48" />
        <div className="h-40 bg-muted rounded animate-pulse" />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="p-6">
        <p className="text-muted-foreground">User not found.</p>
      </div>
    );
  }

  const govRoles = user.governance_roles ?? [];
  const displayName = player?.full_name ?? user.email.split("@")[0];

  return (
    <div className="space-y-6 max-w-2xl">
      <button
        onClick={() => router.back()}
        className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Users
      </button>

      {/* Profile card — player photo if available, all role badges */}
      <div className="rounded-xl border border-border bg-card p-6">
        <div className="flex items-start gap-5">
          {/* Avatar: player photo > initials */}
          <div className="w-16 h-16 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xl font-bold overflow-hidden ring-2 ring-border shrink-0">
            {player?.photo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={player.photo_url}
                alt={player.full_name}
                className="w-full h-full object-cover"
              />
            ) : (
              <User className="h-7 w-7" />
            )}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-lg font-semibold truncate">{displayName}</h1>
              {user.force_password_change && (
                <span className="text-[10px] bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded-sm dark:bg-amber-900/30 dark:text-amber-400">
                  pw change pending
                </span>
              )}
            </div>

            {/* All role badges */}
            <div className="flex items-center gap-1.5 flex-wrap mt-2">
              {user.member_type && <StatusBadge status={user.member_type} />}
              {govRoles.map((gr, i) => (
                <StatusBadge key={`${gr.role}-${i}`} status={gr.role} />
              ))}
              {!user.member_type && govRoles.length === 0 && (
                <StatusBadge status={user.role} />
              )}
              <StatusBadge status={user.is_active ? "active" : "inactive"} />
            </div>
          </div>
        </div>
      </div>

      {/* Detail grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="rounded-lg border border-border bg-card p-4 flex items-start gap-3">
          <Mail className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
          <div>
            <p className="text-xs text-muted-foreground">Email</p>
            <p className="text-sm font-medium mt-0.5 break-all">{user.email}</p>
          </div>
        </div>

        <div className="rounded-lg border border-border bg-card p-4 flex items-start gap-3">
          <Shield className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
          <div>
            <p className="text-xs text-muted-foreground">Primary role</p>
            <p className="text-sm font-medium mt-0.5 capitalize">
              {user.role.replace(/_/g, " ")}
            </p>
          </div>
        </div>

        <div className="rounded-lg border border-border bg-card p-4 flex items-start gap-3">
          <Calendar className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
          <div>
            <p className="text-xs text-muted-foreground">Joined</p>
            <p className="text-sm font-medium mt-0.5">{formatDate(user.created_at)}</p>
          </div>
        </div>

        <div className="rounded-lg border border-border bg-card p-4 flex items-start gap-3">
          <Calendar className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
          <div>
            <p className="text-xs text-muted-foreground">Last login</p>
            <p className="text-sm font-medium mt-0.5">
              {user.last_login_at ? formatRelative(user.last_login_at) : "Never"}
            </p>
          </div>
        </div>
      </div>

      {/* Club */}
      {club && (
        <div>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
            Club
          </p>
          <button
            onClick={() => router.push(`/dashboard/clubs/${club.id}`)}
            className="flex items-center gap-3 p-4 rounded-lg border border-border bg-card hover:bg-muted/50 transition-colors w-full text-left"
          >
            <div className="w-10 h-10 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0 overflow-hidden">
              {club.logo_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={club.logo_url} alt={club.name} className="w-full h-full object-cover" />
              ) : (
                <Building2 className="h-5 w-5" />
              )}
            </div>
            <div>
              <p className="text-sm font-medium">{club.name}</p>
              <p className="text-xs text-muted-foreground font-mono">{club.code}</p>
            </div>
          </button>
        </div>
      )}

      {/* Player identity — folded into the account view, not a separate "profile" */}
      {player && (
        <div>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
            Player identity
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="rounded-lg border border-border bg-card p-4">
              <p className="text-xs text-muted-foreground mb-1 flex items-center gap-1.5">
                <Shield className="h-3 w-3" />
                Player code
              </p>
              <p className="text-sm font-mono font-medium">{player.league_player_code}</p>
            </div>
            <div className="rounded-lg border border-border bg-card p-4">
              <p className="text-xs text-muted-foreground mb-1 flex items-center gap-1.5">
                <Calendar className="h-3 w-3" />
                Date of birth
              </p>
              <p className="text-sm font-medium">{player.date_of_birth}</p>
            </div>
            <div className="rounded-lg border border-border bg-card p-4">
              <p className="text-xs text-muted-foreground mb-1">Status</p>
              <StatusBadge status={player.status} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
