"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { ClipboardList, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
import { registrationsApi, playersApi, seasonsApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { PlayerRead, RegistrationRequestRead, SeasonRead } from "@/types";

// ---------------------------------------------------------------------------
// Create dialog — club admin only
// Sends a squad registration request to any club member (including admins and
// the club admin themselves).  Backend scopes the player list to the caller's
// club, so no additional filtering is needed here.
// ---------------------------------------------------------------------------

const schema = z.object({
  player_id: z.number().int().positive("Select a member"),
  season_id: z.number().int().positive("Select a season"),
});
type FormData = z.infer<typeof schema>;

function CreateDialog({
  clubId,
  open,
  onOpenChange,
}: {
  clubId: number;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const queryClient = useQueryClient();
  // Backend automatically scopes GET /players/ to the caller's club when the
  // caller is a club_admin, so this list only shows club members.
  const { data: players } = useQuery<PlayerRead[]>({
    queryKey: ["players"],
    queryFn: playersApi.list,
    enabled: open,
  });
  const { data: seasons } = useQuery<SeasonRead[]>({
    queryKey: ["seasons"],
    queryFn: seasonsApi.list,
    enabled: open,
  });

  const form = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { player_id: 0, season_id: 0 },
  });

  const mutation = useMutation({
    mutationFn: (data: FormData) =>
      registrationsApi.create({
        player_id: data.player_id,
        club_id: clubId,
        season_id: data.season_id,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["registrations"] });
      toast.success("Registration request sent — the member will be notified");
      onOpenChange(false);
      form.reset();
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Send registration request</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground -mt-2">
          The member will see this request and must acknowledge it to be registered for the season.
        </p>
        <form
          onSubmit={form.handleSubmit((d) => mutation.mutate(d))}
          className="space-y-4"
        >
          <div className="space-y-1.5">
            <Label>Member *</Label>
            <Controller
              control={form.control}
              name="player_id"
              render={({ field }) => (
                <Select
                  onValueChange={(v) => field.onChange(Number(v))}
                  value={field.value ? String(field.value) : ""}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select club member" />
                  </SelectTrigger>
                  <SelectContent>
                    {players?.map((p) => (
                      <SelectItem key={p.id} value={String(p.id)}>
                        {p.full_name}
                        <span className="ml-1.5 text-muted-foreground font-mono text-xs">
                          {p.league_player_code}
                        </span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
            {form.formState.errors.player_id && (
              <p className="text-xs text-destructive">
                {form.formState.errors.player_id.message}
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label>Season *</Label>
            <Controller
              control={form.control}
              name="season_id"
              render={({ field }) => (
                <Select
                  onValueChange={(v) => field.onChange(Number(v))}
                  value={field.value ? String(field.value) : ""}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select season" />
                  </SelectTrigger>
                  <SelectContent>
                    {seasons?.map((s) => (
                      <SelectItem key={s.id} value={String(s.id)}>
                        {s.name} ({s.year})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
            {form.formState.errors.season_id && (
              <p className="text-xs text-destructive">
                {form.formState.errors.season_id.message}
              </p>
            )}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Sending…" : "Send request"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Name maps helper
// ---------------------------------------------------------------------------

function useNameMaps() {
  const { data: players = [] } = useQuery<PlayerRead[]>({
    queryKey: ["players"],
    queryFn: playersApi.list,
  });
  const { data: seasons = [] } = useQuery<SeasonRead[]>({
    queryKey: ["seasons"],
    queryFn: seasonsApi.list,
  });
  const playerMap = new Map(players.map((p) => [p.id, p.full_name]));
  const seasonMap = new Map(seasons.map((s) => [s.id, s.name]));
  return { playerMap, seasonMap };
}

// ---------------------------------------------------------------------------
// Club admin view — outgoing squad registration requests
// ---------------------------------------------------------------------------

function ClubAdminView({
  clubId,
  requests,
  playerMap,
  seasonMap,
}: {
  clubId: number;
  requests: RegistrationRequestRead[];
  playerMap: Map<number, string>;
  seasonMap: Map<number, string>;
}) {
  const [createOpen, setCreateOpen] = useState(false);
  const mine = requests.filter((r) => r.club_id === clubId);
  const pending = mine.filter((r) => r.status === "pending_player_confirmation");
  const history = mine.filter((r) => r.status !== "pending_player_confirmation");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div />
        <Button size="sm" onClick={() => setCreateOpen(true)} className="gap-1.5">
          <Plus className="h-4 w-4" />
          Send request
        </Button>
      </div>

      {mine.length === 0 ? (
        <EmptyState
          title="No registration requests sent"
          description="Send a registration request to add any club member to the season squad"
          icon={<ClipboardList className="h-6 w-6" />}
          action={{ label: "Send request", onClick: () => setCreateOpen(true) }}
        />
      ) : (
        <>
          {pending.length > 0 && (
            <RegistrationsTable
              title={`Awaiting acknowledgement (${pending.length})`}
              rows={pending}
              playerMap={playerMap}
              seasonMap={seasonMap}
            />
          )}
          {history.length > 0 && (
            <RegistrationsTable
              title="History"
              rows={history}
              playerMap={playerMap}
              seasonMap={seasonMap}
            />
          )}
        </>
      )}

      <CreateDialog clubId={clubId} open={createOpen} onOpenChange={setCreateOpen} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared table
// ---------------------------------------------------------------------------

function RegistrationsTable({
  title,
  rows,
  playerMap,
  seasonMap,
}: {
  title: string;
  rows: RegistrationRequestRead[];
  playerMap: Map<number, string>;
  seasonMap: Map<number, string>;
}) {
  return (
    <div>
      <h2 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">
        {title}
      </h2>
      <div className="rounded-lg border border-border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Member</TableHead>
              <TableHead>Club</TableHead>
              <TableHead>Season</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Date</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.id} className="hover:bg-muted/50">
                <TableCell className="font-medium">
                  {playerMap.get(r.player_id) ?? `Member ${r.player_id}`}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  Club {r.club_id}
                </TableCell>
                <TableCell className="text-sm">
                  {seasonMap.get(r.season_id) ?? `Season ${r.season_id}`}
                </TableCell>
                <TableCell>
                  <StatusBadge status={r.status} />
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {r.responded_at ? formatDate(r.responded_at) : formatDate(r.created_at)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page — only visible to club admins and league-level admins
// ---------------------------------------------------------------------------

export default function RegistrationsPage() {
  const { user } = useCurrentUser();
  const { playerMap, seasonMap } = useNameMaps();

  const { data: requests = [], isLoading, error, refetch } = useQuery<RegistrationRequestRead[]>({
    queryKey: ["registrations"],
    queryFn: registrationsApi.list,
  });

  const canManage = user?.role === "club_admin" || user?.role === "league_admin" || user?.role === "super_admin";

  return (
    <div>
      <PageHeader
        title="Registrations"
        description="Send squad registration requests to club members for the current season"
      />

      {isLoading ? (
        <DataTableSkeleton columns={5} />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : canManage && user?.club_id ? (
        <ClubAdminView
          clubId={user.club_id}
          requests={requests}
          playerMap={playerMap}
          seasonMap={seasonMap}
        />
      ) : (
        <EmptyState
          title="Registrations"
          description="This area is for club admins to manage squad registrations. Check My Profile for your own registration requests."
          icon={<ClipboardList className="h-6 w-6" />}
        />
      )}
    </div>
  );
}
