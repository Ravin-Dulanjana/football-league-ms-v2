"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertTriangle, CheckCheck, ExternalLink, FileText, Lock, UserMinus } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  ConfirmDialog,
  DataTableSkeleton,
  EmptyState,
  ErrorState,
  PageHeader,
} from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { clubMembershipsApi, releasesApi, playersApi, seasonsApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { PlayerRead, ReleaseRead, SeasonRead } from "@/types";

// ---------------------------------------------------------------------------
// Club admin view — release any club member (no registration required)
// ---------------------------------------------------------------------------

function ClubAdminView({ clubId }: { clubId: number }) {
  const [releaseTarget, setReleaseTarget] = useState<PlayerRead | null>(null);
  const queryClient = useQueryClient();

  const { data: players = [], isLoading: playersLoading } = useQuery<PlayerRead[]>({
    queryKey: ["players"],
    queryFn: playersApi.list,
  });

  const { data: seasons = [] } = useQuery<SeasonRead[]>({
    queryKey: ["seasons"],
    queryFn: seasonsApi.list,
  });

  const seasonLocked = seasons.some((s) => s.status === "active");

  const releaseMutation = useMutation({
    mutationFn: (playerId: number) => clubMembershipsApi.releasePlayer(playerId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["players"] });
      queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
      toast.success("Player released — they are now a free agent");
      setReleaseTarget(null);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const clubPlayers = players.filter((p) => p.club_id === clubId);

  return (
    <div className="space-y-4">
      {seasonLocked && (
        <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30 p-4">
          <Lock className="h-4 w-4 text-amber-600 dark:text-amber-400 mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-medium text-amber-800 dark:text-amber-300">
              Season is active — releases are locked
            </p>
            <p className="text-xs text-amber-700 dark:text-amber-400 mt-0.5">
              Players cannot be released while a season is in progress.
              Releases are only allowed outside of the playing season.
            </p>
          </div>
        </div>
      )}

      {playersLoading ? (
        <DataTableSkeleton columns={3} />
      ) : clubPlayers.length === 0 ? (
        <EmptyState
          title="No players in club"
          description="Invite players to join your club first"
          icon={<UserMinus className="h-6 w-6" />}
        />
      ) : (
        <div className="rounded-lg border border-border overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Code</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Status</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {clubPlayers.map((player) => (
                <TableRow key={player.id}>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {player.league_player_code}
                  </TableCell>
                  <TableCell className="font-medium">{player.full_name}</TableCell>
                  <TableCell>
                    <StatusBadge status={player.status} />
                  </TableCell>
                  <TableCell>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 gap-1 text-xs text-muted-foreground hover:text-destructive"
                      disabled={seasonLocked}
                      onClick={() => setReleaseTarget(player)}
                    >
                      <UserMinus className="h-3.5 w-3.5" />
                      Release
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {releaseTarget && (
        <ConfirmDialog
          open
          onOpenChange={(v) => { if (!v) setReleaseTarget(null); }}
          title="Release player?"
          description={`Release ${releaseTarget.full_name} from your club? They will become a free agent and can be invited by any club.`}
          confirmLabel="Release player"
          destructive
          loading={releaseMutation.isPending}
          onConfirm={() => releaseMutation.mutate(releaseTarget.id)}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Player view — incoming release notices with Acknowledge button
// ---------------------------------------------------------------------------

function PlayerView({
  playerId,
  releases,
  playerMap,
}: {
  playerId: number;
  releases: ReleaseRead[];
  playerMap: Map<number, PlayerRead>;
}) {
  const [ackTarget, setAckTarget] = useState<number | null>(null);
  const queryClient = useQueryClient();

  const ackMutation = useMutation({
    mutationFn: (id: number) => releasesApi.decide(id, "confirm"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["releases"] });
      toast.success("Release acknowledged");
      setAckTarget(null);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const mine = releases.filter((r) => r.player_id === playerId);
  const pending = mine.filter((r) => r.status === "pending_player_confirmation");
  const history = mine.filter((r) => r.status !== "pending_player_confirmation");

  if (mine.length === 0) {
    return (
      <EmptyState
        title="No release notices"
        description="Release notices from your club will appear here"
        icon={<FileText className="h-6 w-6" />}
      />
    );
  }

  return (
    <div className="space-y-6">
      {pending.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">
            Awaiting your acknowledgement ({pending.length})
          </h2>
          <div className="space-y-3">
            {pending.map((r) => (
              <div
                key={r.id}
                className="flex items-start justify-between p-4 rounded-lg border border-border bg-card gap-4"
              >
                <div className="space-y-1 min-w-0">
                  <p className="text-sm font-medium">
                    Release from Club {r.from_club_id}
                  </p>
                  {r.effective_date && (
                    <p className="text-xs text-muted-foreground">
                      Effective: {formatDate(r.effective_date)}
                    </p>
                  )}
                  {r.documents.length > 0 && (
                    <div className="flex flex-col gap-1 mt-1">
                      {r.documents.map((doc) => (
                        <a
                          key={doc.id}
                          href={doc.file_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1 text-xs text-primary hover:underline"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <FileText className="h-3 w-3" />
                          {doc.file_name}
                          <ExternalLink className="h-2.5 w-2.5" />
                        </a>
                      ))}
                    </div>
                  )}
                  <p className="text-xs text-muted-foreground">
                    Received {formatDate(r.created_at)}
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  className="gap-1.5 shrink-0"
                  onClick={() => setAckTarget(r.id)}
                >
                  <CheckCheck className="h-3.5 w-3.5" />
                  Acknowledge
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      {history.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">
            History
          </h2>
          <div className="rounded-lg border border-border overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Club</TableHead>
                  <TableHead>Effective date</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Date</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {history.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="font-medium">Club {r.from_club_id}</TableCell>
                    <TableCell className="text-sm">
                      {r.effective_date ? formatDate(r.effective_date) : "—"}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={r.status} />
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {r.confirmed_at ? formatDate(r.confirmed_at) : formatDate(r.created_at)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      {ackTarget !== null && (
        <ConfirmDialog
          open
          onOpenChange={(v) => { if (!v) setAckTarget(null); }}
          title="Acknowledge release?"
          description="By acknowledging, you confirm you have been released from the club. This cannot be undone."
          confirmLabel="Acknowledge release"
          destructive
          loading={ackMutation.isPending}
          onConfirm={() => ackMutation.mutate(ackTarget!)}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ReleasesPage() {
  const { user } = useCurrentUser();
  // Only pure club_admin role manages the club's outgoing releases.
  // League admins (even with club_admin governance) see only their own player releases.
  const isPureClubAdmin = user?.role === "club_admin";

  const { data: releases = [], isLoading, error, refetch } = useQuery<ReleaseRead[]>({
    queryKey: ["releases"],
    queryFn: releasesApi.list,
    enabled: !isPureClubAdmin,
  });

  const { data: players = [] } = useQuery<PlayerRead[]>({
    queryKey: ["players"],
    queryFn: playersApi.list,
    enabled: !isPureClubAdmin,
  });
  const playerMap = new Map(players.map((p) => [p.id, p]));

  return (
    <div>
      <PageHeader
        title="Releases"
        description={
          isPureClubAdmin
            ? "Release players from your club"
            : "Release notices from your club"
        }
      />

      {isPureClubAdmin && user?.club_id ? (
        <ClubAdminView clubId={user.club_id} />
      ) : isLoading ? (
        <DataTableSkeleton columns={4} />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : user?.player_id ? (
        <PlayerView
          playerId={user.player_id}
          releases={releases}
          playerMap={playerMap}
        />
      ) : (
        <EmptyState
          title="No release notices"
          description="Release notices from your club will appear here"
          icon={<FileText className="h-6 w-6" />}
        />
      )}
    </div>
  );
}
