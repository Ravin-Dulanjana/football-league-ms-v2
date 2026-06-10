"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Calendar, CreditCard, Hash } from "lucide-react";

import { StatusBadge } from "@/components/shared/StatusBadge";
import { playersApi, clubsApi, registrationsApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { ClubRead, PlayerRead, RegistrationRequestRead } from "@/types";

export default function PlayerDetailPage() {
  const params = useParams();
  const router = useRouter();
  const playerId = Number(params.id);

  const { data: player, isLoading } = useQuery<PlayerRead>({
    queryKey: ["player", playerId],
    queryFn: () => playersApi.get(playerId),
  });

  const { data: allRegistrations = [] } = useQuery<RegistrationRequestRead[]>({
    queryKey: ["registrations"],
    queryFn: registrationsApi.list,
    enabled: !!player,
  });

  const { data: allClubs = [] } = useQuery<ClubRead[]>({
    queryKey: ["clubs"],
    queryFn: clubsApi.list,
    enabled: allRegistrations.length > 0,
  });

  const acceptedReg = allRegistrations.find(
    (r) => r.player_id === playerId && r.status === "accepted"
  );
  const currentClub = acceptedReg
    ? allClubs.find((c) => c.id === acceptedReg.club_id)
    : null;

  const initials = player?.full_name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <div className="h-8 bg-muted rounded animate-pulse w-48" />
        <div className="h-40 bg-muted rounded animate-pulse" />
      </div>
    );
  }

  if (!player) {
    return (
      <div className="p-6">
        <p className="text-muted-foreground">Player not found.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <button
        onClick={() => router.back()}
        className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Players
      </button>

      {/* Profile card */}
      <div className="rounded-xl border border-border bg-card p-6">
        <div className="flex items-start gap-5">
          {/* Avatar */}
          <div className="relative shrink-0">
            {player.photo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={player.photo_url}
                alt={player.full_name}
                className="w-20 h-20 rounded-full object-cover ring-2 ring-border"
              />
            ) : (
              <div className="w-20 h-20 rounded-full bg-primary/10 text-primary flex items-center justify-center text-2xl font-bold ring-2 ring-border">
                {initials}
              </div>
            )}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-xl font-semibold">{player.full_name}</h1>
              <StatusBadge status={player.status} />
            </div>
            <p className="font-mono text-sm text-muted-foreground mt-0.5">
              {player.league_player_code}
            </p>
            {currentClub && (
              <button
                onClick={() => router.push(`/dashboard/clubs/${currentClub.id}`)}
                className="mt-2 flex items-center gap-1.5 text-sm text-primary hover:underline"
              >
                {currentClub.name}
                <span className="font-mono text-xs text-muted-foreground">
                  ({currentClub.code})
                </span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Detail grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="rounded-lg border border-border bg-card p-4 flex items-start gap-3">
          <Calendar className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
          <div>
            <p className="text-xs text-muted-foreground">Date of birth</p>
            <p className="text-sm font-medium mt-0.5">{formatDate(player.date_of_birth)}</p>
          </div>
        </div>

        <div className="rounded-lg border border-border bg-card p-4 flex items-start gap-3">
          <CreditCard className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
          <div>
            <p className="text-xs text-muted-foreground">NIC number</p>
            <p className="text-sm font-medium font-mono mt-0.5">{player.nic_number}</p>
          </div>
        </div>

        <div className="rounded-lg border border-border bg-card p-4 flex items-start gap-3">
          <Hash className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
          <div>
            <p className="text-xs text-muted-foreground">Player code</p>
            <p className="text-sm font-medium font-mono mt-0.5">{player.league_player_code}</p>
          </div>
        </div>

        <div className="rounded-lg border border-border bg-card p-4 flex items-start gap-3">
          <Calendar className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
          <div>
            <p className="text-xs text-muted-foreground">Registered</p>
            <p className="text-sm font-medium mt-0.5">{formatDate(player.created_at)}</p>
          </div>
        </div>
      </div>

      {/* Current club */}
      {currentClub && (
        <div>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
            Current club
          </p>
          <button
            onClick={() => router.push(`/dashboard/clubs/${currentClub.id}`)}
            className="flex items-center gap-3 p-4 rounded-lg border border-border bg-card hover:bg-muted/50 transition-colors w-full text-left"
          >
            <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-primary/10 text-primary font-bold text-sm shrink-0">
              {currentClub.code.slice(0, 3)}
            </div>
            <div>
              <p className="text-sm font-medium">{currentClub.name}</p>
              <p className="text-xs text-muted-foreground font-mono">{currentClub.code}</p>
            </div>
          </button>
        </div>
      )}
    </div>
  );
}
