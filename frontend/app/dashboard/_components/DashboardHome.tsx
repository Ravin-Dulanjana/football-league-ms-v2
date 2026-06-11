"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Building2,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  FileText,
  Shirt,
} from "lucide-react";

import { useCurrentUser } from "@/hooks/useCurrentUser";
import { clubsApi, reportsApi, registrationsApi, releasesApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { formatRelative } from "@/lib/utils";
import type { AnalyticsSummary, ClubRead, RegistrationRequestRead, ReleaseRead } from "@/types";

// ---------------------------------------------------------------------------
// Stat card
// ---------------------------------------------------------------------------

function StatCard({
  title,
  value,
  icon: Icon,
  href,
  loading,
}: {
  title: string;
  value: number | undefined;
  icon: React.ElementType;
  href: string;
  loading: boolean;
}) {
  return (
    <Link href={href} className="group">
      <Card className="transition-colors hover:border-primary/50">
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
          <Icon className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" />
        </CardHeader>
        <CardContent>
          {loading ? (
            <Skeleton className="h-8 w-16" />
          ) : (
            <p className="text-3xl font-bold tabular-nums">{value ?? "—"}</p>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}

// ---------------------------------------------------------------------------
// Club banner — shown at top for any user who belongs to a club
// ---------------------------------------------------------------------------

function ClubBanner({ clubId }: { clubId: number }) {
  const { data: club, isLoading } = useQuery<ClubRead>({
    queryKey: ["club", clubId],
    queryFn: () => clubsApi.get(clubId),
    staleTime: 5 * 60 * 1000,
  });

  if (isLoading) {
    return (
      <div className="flex items-center gap-3 p-4 rounded-xl border border-border bg-card">
        <Skeleton className="w-10 h-10 rounded-lg" />
        <div className="space-y-1.5">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-3 w-20" />
        </div>
      </div>
    );
  }
  if (!club) return null;

  return (
    <Link
      href={`/dashboard/clubs/${club.id}`}
      className="flex items-center gap-3 p-4 rounded-xl border border-border bg-card hover:bg-muted/50 transition-colors"
    >
      <div className="w-10 h-10 rounded-lg bg-primary/10 text-primary font-bold flex items-center justify-center text-xs shrink-0 overflow-hidden">
        {club.logo_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={club.logo_url} alt={club.name} className="w-full h-full object-cover" />
        ) : (
          <Building2 className="h-5 w-5" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold truncate">{club.name}</p>
        <p className="text-xs text-muted-foreground">
          {club.short_name ?? club.code}
          {club.established_year ? ` · Est. ${club.established_year}` : ""}
        </p>
      </div>
      <StatusBadge status={club.status} />
      <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
    </Link>
  );
}

// ---------------------------------------------------------------------------
// League admin / super admin dashboard
// ---------------------------------------------------------------------------

function AdminDashboard() {
  const { data: analytics, isLoading } = useQuery<AnalyticsSummary>({
    queryKey: ["analytics"],
    queryFn: reportsApi.analytics,
    staleTime: 60 * 1000,
  });

  const { data: pendingRegs, isLoading: regsLoading } = useQuery<RegistrationRequestRead[]>({
    queryKey: ["registrations"],
    queryFn: registrationsApi.list,
    staleTime: 30 * 1000,
  });

  const { data: pendingReleases, isLoading: releasesLoading } = useQuery<ReleaseRead[]>({
    queryKey: ["releases"],
    queryFn: releasesApi.list,
    staleTime: 30 * 1000,
  });

  const openRegs = pendingRegs?.filter((r) => r.status === "pending_player_confirmation") ?? [];
  const openReleases = pendingReleases?.filter((r) => r.status === "pending_player_confirmation") ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-sm text-muted-foreground mt-1">League overview</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total clubs"
          value={analytics?.total_clubs}
          icon={Building2}
          href="/dashboard/clubs"
          loading={isLoading}
        />
        <StatCard
          title="Active players"
          value={analytics?.active_players}
          icon={Shirt}
          href="/dashboard/players"
          loading={isLoading}
        />
        <StatCard
          title="Pending registrations"
          value={analytics?.pending_registration_requests}
          icon={ClipboardList}
          href="/dashboard/registrations"
          loading={isLoading}
        />
        <StatCard
          title="Pending releases"
          value={analytics?.pending_releases}
          icon={FileText}
          href="/dashboard/releases"
          loading={isLoading}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="text-sm font-semibold">Registration requests</CardTitle>
            <Link
              href="/dashboard/registrations"
              className="text-xs text-muted-foreground hover:text-primary flex items-center gap-0.5 transition-colors"
            >
              View all <ChevronRight className="h-3 w-3" />
            </Link>
          </CardHeader>
          <CardContent>
            {regsLoading ? (
              <div className="space-y-2">
                {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-10" />)}
              </div>
            ) : openRegs.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">No open requests</p>
            ) : (
              <ul className="space-y-2">
                {openRegs.slice(0, 5).map((r) => (
                  <li key={r.id} className="flex items-center justify-between py-1.5 border-b border-border last:border-0">
                    <div>
                      <p className="text-sm font-medium">Request #{r.id}</p>
                      <p className="text-xs text-muted-foreground">
                        Player {r.player_id} · {formatRelative(r.created_at)}
                      </p>
                    </div>
                    <StatusBadge status={r.status} />
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="text-sm font-semibold">Release requests</CardTitle>
            <Link
              href="/dashboard/releases"
              className="text-xs text-muted-foreground hover:text-primary flex items-center gap-0.5 transition-colors"
            >
              View all <ChevronRight className="h-3 w-3" />
            </Link>
          </CardHeader>
          <CardContent>
            {releasesLoading ? (
              <div className="space-y-2">
                {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-10" />)}
              </div>
            ) : openReleases.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">No open releases</p>
            ) : (
              <ul className="space-y-2">
                {openReleases.slice(0, 5).map((r) => (
                  <li key={r.id} className="flex items-center justify-between py-1.5 border-b border-border last:border-0">
                    <div>
                      <p className="text-sm font-medium">Release #{r.id}</p>
                      <p className="text-xs text-muted-foreground">
                        Player {r.player_id} · {formatRelative(r.created_at)}
                      </p>
                    </div>
                    <StatusBadge status={r.status} />
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Club admin dashboard
// ---------------------------------------------------------------------------

function ClubAdminDashboard() {
  const { user } = useCurrentUser();

  const { data: regs, isLoading: regsLoading } = useQuery<RegistrationRequestRead[]>({
    queryKey: ["registrations"],
    queryFn: registrationsApi.list,
    staleTime: 30 * 1000,
  });

  const { data: releases, isLoading: releasesLoading } = useQuery<ReleaseRead[]>({
    queryKey: ["releases"],
    queryFn: releasesApi.list,
    staleTime: 30 * 1000,
  });

  const pendingRegs = regs?.filter((r) => r.status === "pending_player_confirmation") ?? [];
  const pendingReleases = releases?.filter((r) => r.status === "pending_player_confirmation") ?? [];

  const loading = regsLoading || releasesLoading;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-sm text-muted-foreground mt-1">Pending actions for your club</p>
      </div>

      {user?.club_id && <ClubBanner clubId={user.club_id} />}

      <div className="grid grid-cols-2 gap-4">
        <StatCard
          title="Pending registrations"
          value={pendingRegs.length}
          icon={ClipboardList}
          href="/dashboard/registrations"
          loading={loading}
        />
        <StatCard
          title="Pending releases"
          value={pendingReleases.length}
          icon={FileText}
          href="/dashboard/releases"
          loading={loading}
        />
      </div>

      <PendingDecisionsList
        registrations={pendingRegs}
        releases={pendingReleases}
        loading={loading}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Player dashboard
// ---------------------------------------------------------------------------

function PlayerDashboard() {
  const { user } = useCurrentUser();

  const { data: regs, isLoading: regsLoading } = useQuery<RegistrationRequestRead[]>({
    queryKey: ["registrations"],
    queryFn: registrationsApi.list,
    staleTime: 30 * 1000,
  });

  const { data: releases, isLoading: releasesLoading } = useQuery<ReleaseRead[]>({
    queryKey: ["releases"],
    queryFn: releasesApi.list,
    staleTime: 30 * 1000,
  });

  const pendingRegs = regs?.filter((r) => r.status === "pending_player_confirmation") ?? [];
  const pendingReleases = releases?.filter((r) => r.status === "pending_player_confirmation") ?? [];

  const loading = regsLoading || releasesLoading;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">My Dashboard</h1>
        <p className="text-sm text-muted-foreground mt-1">Decisions waiting for you</p>
      </div>

      {user?.club_id && <ClubBanner clubId={user.club_id} />}

      <PendingDecisionsList
        registrations={pendingRegs}
        releases={pendingReleases}
        loading={loading}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared pending decisions list (club admin + player)
// ---------------------------------------------------------------------------

function PendingDecisionsList({
  registrations,
  releases,
  loading,
}: {
  registrations: RegistrationRequestRead[];
  releases: ReleaseRead[];
  loading: boolean;
}) {
  const hasItems = registrations.length > 0 || releases.length > 0;

  if (loading) {
    return (
      <Card>
        <CardContent className="pt-4 space-y-3">
          {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-12" />)}
        </CardContent>
      </Card>
    );
  }

  if (!hasItems) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12 gap-2">
          <CheckCircle2 className="h-8 w-8 text-green-500" />
          <p className="text-sm font-medium">All caught up</p>
          <p className="text-xs text-muted-foreground">No pending decisions at the moment</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {registrations.length > 0 && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="text-sm font-semibold">Registration requests</CardTitle>
            <Link href="/dashboard/registrations" className="text-xs text-muted-foreground hover:text-primary flex items-center gap-0.5 transition-colors">
              View all <ChevronRight className="h-3 w-3" />
            </Link>
          </CardHeader>
          <CardContent className="pt-0">
            <ul className="divide-y divide-border">
              {registrations.slice(0, 5).map((r) => (
                <li key={r.id} className="flex items-center justify-between py-3">
                  <div>
                    <p className="text-sm font-medium">Registration request #{r.id}</p>
                    <p className="text-xs text-muted-foreground">{formatRelative(r.created_at)}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusBadge status={r.status} />
                    <Link href="/dashboard/registrations">
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    </Link>
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {releases.length > 0 && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="text-sm font-semibold">Release requests</CardTitle>
            <Link href="/dashboard/releases" className="text-xs text-muted-foreground hover:text-primary flex items-center gap-0.5 transition-colors">
              View all <ChevronRight className="h-3 w-3" />
            </Link>
          </CardHeader>
          <CardContent className="pt-0">
            <ul className="divide-y divide-border">
              {releases.slice(0, 5).map((r) => (
                <li key={r.id} className="flex items-center justify-between py-3">
                  <div>
                    <p className="text-sm font-medium">Release request #{r.id}</p>
                    <p className="text-xs text-muted-foreground">{formatRelative(r.created_at)}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusBadge status={r.status} />
                    <Link href="/dashboard/releases">
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    </Link>
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Root export — role switch
// ---------------------------------------------------------------------------

export function DashboardHome() {
  const { role, isLoading } = useCurrentUser();

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-28" />)}
        </div>
      </div>
    );
  }

  if (role === "super_admin" || role === "league_admin") return <AdminDashboard />;
  if (role === "club_admin") return <ClubAdminDashboard />;
  return <PlayerDashboard />;
}
