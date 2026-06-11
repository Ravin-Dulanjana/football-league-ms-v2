"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Check, Users, UserMinus, UserPlus, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DataTableSkeleton,
  EmptyState,
  ErrorState,
  PageHeader,
} from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { clubMembershipsApi, clubsApi, playersApi } from "@/lib/api";
import { formatRelative } from "@/lib/utils";
import type { ClubMembershipRequestRead, ClubRead, PlayerRead } from "@/types";

// ---------------------------------------------------------------------------
// Invite dialog
// ---------------------------------------------------------------------------

function InviteDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [selectedPlayerId, setSelectedPlayerId] = useState<number | null>(null);

  const { data: freePlayers, isLoading } = useQuery<PlayerRead[]>({
    queryKey: ["club-memberships", "free-players"],
    queryFn: clubMembershipsApi.listFreePlayers,
    enabled: open,
  });

  const mutation = useMutation({
    mutationFn: () => clubMembershipsApi.invite({ player_id: selectedPlayerId! }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["club-memberships"] });
      toast.success("Invite sent — the player will see it on their dashboard");
      onOpenChange(false);
      setSelectedPlayerId(null);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Invite a player to join</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground -mt-2">
          Only free players (not currently in any club) can be invited.
          They must accept before they appear on your roster.
        </p>
        <div className="space-y-1.5">
          <Label>Player *</Label>
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading free players…</p>
          ) : !freePlayers?.length ? (
            <p className="text-sm text-muted-foreground">
              No free players available. All players are currently in a club.
            </p>
          ) : (
            <Select
              value={selectedPlayerId ? String(selectedPlayerId) : ""}
              onValueChange={(v) => setSelectedPlayerId(Number(v))}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a player" />
              </SelectTrigger>
              <SelectContent>
                {freePlayers.map((p) => (
                  <SelectItem key={p.id} value={String(p.id)}>
                    {p.full_name}{" "}
                    <span className="text-xs text-muted-foreground">({p.league_player_code})</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button
            disabled={!selectedPlayerId || mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {mutation.isPending ? "Sending…" : "Send invite"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Release confirmation
// ---------------------------------------------------------------------------

function ReleaseDialog({
  player,
  open,
  onOpenChange,
}: {
  player: PlayerRead | null;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => clubMembershipsApi.releasePlayer(player!.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["club-memberships"] });
      queryClient.invalidateQueries({ queryKey: ["players"] });
      toast.success(`${player?.full_name} released from club`);
      onOpenChange(false);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Release player</DialogTitle>
        </DialogHeader>
        <p className="text-sm">
          Release <strong>{player?.full_name}</strong> from your club?
        </p>
        <p className="text-sm text-muted-foreground">
          They will become a free player and can be invited by any club.
          This does not remove their season registration records.
        </p>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button
            variant="destructive"
            disabled={mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {mutation.isPending ? "Releasing…" : "Release player"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

type Tab = "roster" | "invites";

export default function ClubMembershipsPage() {
  const [tab, setTab] = useState<Tab>("roster");
  const [inviteOpen, setInviteOpen] = useState(false);
  const [releaseTarget, setReleaseTarget] = useState<PlayerRead | null>(null);
  const { isClubAdmin, isLeagueLevel, user: currentUser } = useCurrentUser();

  const { data: clubs } = useQuery<ClubRead[]>({
    queryKey: ["clubs"],
    queryFn: clubsApi.list,
    enabled: isLeagueLevel,
  });

  const clubMap = Object.fromEntries((clubs ?? []).map((c) => [c.id, c.name]));

  const { data: players, isLoading: playersLoading, error: playersError, refetch: refetchPlayers } =
    useQuery<PlayerRead[]>({
      queryKey: ["players"],
      queryFn: playersApi.list,
    });

  const { data: requests, isLoading: reqLoading, error: reqError, refetch: refetchReqs } =
    useQuery<ClubMembershipRequestRead[]>({
      queryKey: ["club-memberships", "requests"],
      queryFn: clubMembershipsApi.listRequests,
    });

  const cancelMutation = useMutation({
    mutationFn: (id: number) => clubMembershipsApi.cancel(id),
    onSuccess: () => {
      toast.success("Invite cancelled");
      queryClient.invalidateQueries({ queryKey: ["club-memberships"] });
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const queryClient = useQueryClient();

  const clubPlayers = players?.filter((p) => {
    if (isClubAdmin && currentUser?.club_id) return p.club_id === currentUser.club_id;
    return p.club_id !== null;
  }) ?? [];

  const pendingRequests = requests?.filter((r) => r.status === "pending") ?? [];
  const pastRequests = requests?.filter((r) => r.status !== "pending") ?? [];

  return (
    <div>
      <PageHeader
        title="Club Roster"
        description="Manage who is in your club and send invites to free players"
        action={
          isClubAdmin ? (
            <Button size="sm" onClick={() => setInviteOpen(true)} className="gap-1.5">
              <UserPlus className="h-4 w-4" />
              Invite player
            </Button>
          ) : undefined
        }
      />

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-border">
        {(["roster", "invites"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={[
              "px-4 py-2 text-sm font-medium -mb-px border-b-2 transition-colors capitalize",
              tab === t
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground",
            ].join(" ")}
          >
            {t}
            {t === "invites" && pendingRequests.length > 0 && (
              <span className="ml-1.5 rounded-full bg-primary text-primary-foreground text-[10px] px-1.5 py-0.5">
                {pendingRequests.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {tab === "roster" && (
        playersLoading ? (
          <DataTableSkeleton columns={4} />
        ) : playersError ? (
          <ErrorState message={(playersError as Error).message} onRetry={() => refetchPlayers()} />
        ) : !clubPlayers.length ? (
          <EmptyState
            title="No players in roster"
            description="Invite a free player to join your club"
            icon={<Users className="h-6 w-6" />}
            action={
              isClubAdmin
                ? { label: "Invite player", onClick: () => setInviteOpen(true) }
                : undefined
            }
          />
        ) : (
          <div className="rounded-lg border border-border overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Name</TableHead>
                  {isLeagueLevel && <TableHead>Club</TableHead>}
                  <TableHead>Status</TableHead>
                  {isClubAdmin && <TableHead />}
                </TableRow>
              </TableHeader>
              <TableBody>
                {clubPlayers.map((player) => (
                  <TableRow key={player.id}>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {player.league_player_code}
                    </TableCell>
                    <TableCell className="font-medium">{player.full_name}</TableCell>
                    {isLeagueLevel && (
                      <TableCell className="text-sm text-muted-foreground">
                        {player.club_id ? (clubMap[player.club_id] ?? `Club ${player.club_id}`) : "—"}
                      </TableCell>
                    )}
                    <TableCell>
                      <StatusBadge status={player.status} />
                    </TableCell>
                    {isClubAdmin && (
                      <TableCell>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 gap-1 text-xs text-muted-foreground hover:text-destructive"
                          onClick={() => setReleaseTarget(player)}
                        >
                          <UserMinus className="h-3.5 w-3.5" />
                          Release
                        </Button>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )
      )}

      {tab === "invites" && (
        reqLoading ? (
          <DataTableSkeleton columns={4} />
        ) : reqError ? (
          <ErrorState message={(reqError as Error).message} onRetry={() => refetchReqs()} />
        ) : !requests?.length ? (
          <EmptyState
            title="No invites yet"
            icon={<UserPlus className="h-6 w-6" />}
            action={
              isClubAdmin
                ? { label: "Send first invite", onClick: () => setInviteOpen(true) }
                : undefined
            }
          />
        ) : (
          <div className="space-y-4">
            {pendingRequests.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                  Pending
                </p>
                <div className="rounded-lg border border-border overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Player ID</TableHead>
                        <TableHead>Sent</TableHead>
                        <TableHead />
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {pendingRequests.map((req) => (
                        <TableRow key={req.id}>
                          <TableCell className="font-mono text-sm">#{req.player_id}</TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {formatRelative(req.created_at)}
                          </TableCell>
                          <TableCell>
                            {isClubAdmin && (
                              <Button
                                size="sm"
                                variant="ghost"
                                className="h-7 gap-1 text-xs text-muted-foreground hover:text-destructive"
                                onClick={() => cancelMutation.mutate(req.id)}
                                disabled={cancelMutation.isPending}
                              >
                                <X className="h-3 w-3" />
                                Cancel
                              </Button>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>
            )}

            {pastRequests.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                  History
                </p>
                <div className="rounded-lg border border-border overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Player ID</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Responded</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {pastRequests.map((req) => (
                        <TableRow key={req.id}>
                          <TableCell className="font-mono text-sm">#{req.player_id}</TableCell>
                          <TableCell>
                            <StatusBadge status={req.status} />
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {req.responded_at ? formatRelative(req.responded_at) : "—"}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>
            )}
          </div>
        )
      )}

      <InviteDialog open={inviteOpen} onOpenChange={setInviteOpen} />
      {releaseTarget && (
        <ReleaseDialog
          player={releaseTarget}
          open={!!releaseTarget}
          onOpenChange={(v) => { if (!v) setReleaseTarget(null); }}
        />
      )}
    </div>
  );
}
