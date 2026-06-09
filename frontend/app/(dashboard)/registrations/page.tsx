"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Check, ClipboardList, Plus, X } from "lucide-react";

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
  ConfirmDialog,
  DataTableSkeleton,
  EmptyState,
  ErrorState,
  PageHeader,
} from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { registrationsApi, clubsApi, playersApi, seasonsApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type {
  ClubRead,
  PlayerRead,
  RegistrationRequestRead,
  SeasonRead,
} from "@/types";

// ---------------------------------------------------------------------------
// Create dialog
// ---------------------------------------------------------------------------

const schema = z.object({
  player_id: z.number().int().positive("Select a player"),
  club_id: z.number().int().positive("Select a club"),
  season_id: z.number().int().positive("Select a season"),
});

type FormData = z.infer<typeof schema>;

function CreateDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const queryClient = useQueryClient();

  const { data: players } = useQuery<PlayerRead[]>({
    queryKey: ["players"],
    queryFn: playersApi.list,
  });
  const { data: clubs } = useQuery<ClubRead[]>({
    queryKey: ["clubs"],
    queryFn: clubsApi.list,
  });
  const { data: seasons } = useQuery<SeasonRead[]>({
    queryKey: ["seasons"],
    queryFn: seasonsApi.list,
  });

  const form = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { player_id: 0, club_id: 0, season_id: 0 },
  });

  const mutation = useMutation({
    mutationFn: (data: FormData) =>
      registrationsApi.create({
        player_id: data.player_id,
        club_id: data.club_id,
        season_id: data.season_id,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["registrations"] });
      toast.success("Registration request created");
      onOpenChange(false);
      form.reset();
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New registration request</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={form.handleSubmit((d) => mutation.mutate(d))}
          className="space-y-4"
        >
          <div className="space-y-1.5">
            <Label>Player *</Label>
            <Controller
              control={form.control}
              name="player_id"
              render={({ field }) => (
                <Select
                  onValueChange={(v) => field.onChange(Number(v))}
                  value={field.value ? String(field.value) : ""}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select player" />
                  </SelectTrigger>
                  <SelectContent>
                    {players?.map((p) => (
                      <SelectItem key={p.id} value={String(p.id)}>
                        {p.full_name} ({p.league_player_code})
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
            <Label>Club *</Label>
            <Controller
              control={form.control}
              name="club_id"
              render={({ field }) => (
                <Select
                  onValueChange={(v) => field.onChange(Number(v))}
                  value={field.value ? String(field.value) : ""}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select club" />
                  </SelectTrigger>
                  <SelectContent>
                    {clubs?.map((c) => (
                      <SelectItem key={c.id} value={String(c.id)}>
                        {c.name} ({c.code})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
            {form.formState.errors.club_id && (
              <p className="text-xs text-destructive">
                {form.formState.errors.club_id.message}
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
              {mutation.isPending ? "Creating…" : "Create request"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function RegistrationsPage() {
  const [createOpen, setCreateOpen] = useState(false);
  const [decideTarget, setDecideTarget] = useState<{
    id: number;
    decision: "accept" | "reject";
  } | null>(null);
  const queryClient = useQueryClient();
  const { isAnyAdmin, isPlayer } = useCurrentUser();

  const { data: requests, isLoading, error, refetch } = useQuery<RegistrationRequestRead[]>({
    queryKey: ["registrations"],
    queryFn: registrationsApi.list,
  });

  const decideMutation = useMutation({
    mutationFn: ({ id, decision }: { id: number; decision: "accept" | "reject" }) =>
      registrationsApi.decide(id, decision),
    onSuccess: (_, { decision }) => {
      queryClient.invalidateQueries({ queryKey: ["registrations"] });
      toast.success(decision === "accept" ? "Registration accepted" : "Registration rejected");
      setDecideTarget(null);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const pending = requests?.filter((r) => r.status === "pending_player_confirmation") ?? [];
  const historical = requests?.filter((r) => r.status !== "pending_player_confirmation") ?? [];

  return (
    <div>
      <PageHeader
        title="Registrations"
        description="Player registration requests"
        action={
          isAnyAdmin ? (
            <Button size="sm" onClick={() => setCreateOpen(true)} className="gap-1.5">
              <Plus className="h-4 w-4" />
              New request
            </Button>
          ) : undefined
        }
      />

      {isLoading ? (
        <DataTableSkeleton columns={6} />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : !requests?.length ? (
        <EmptyState
          title="No registration requests"
          description="No requests have been made yet"
          icon={<ClipboardList className="h-6 w-6" />}
          action={
            isAnyAdmin ? { label: "New request", onClick: () => setCreateOpen(true) } : undefined
          }
        />
      ) : (
        <div className="space-y-6">
          {pending.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">
                Awaiting decision ({pending.length})
              </h2>
              <div className="rounded-lg border border-border overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>ID</TableHead>
                      <TableHead>Player</TableHead>
                      <TableHead>Club</TableHead>
                      <TableHead>Season</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Created</TableHead>
                      {isPlayer && <TableHead />}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {pending.map((r) => (
                      <TableRow key={r.id} className="hover:bg-muted/50">
                        <TableCell className="text-muted-foreground">#{r.id}</TableCell>
                        <TableCell>Player {r.player_id}</TableCell>
                        <TableCell>Club {r.club_id}</TableCell>
                        <TableCell>Season {r.season_id}</TableCell>
                        <TableCell>
                          <StatusBadge status={r.status} />
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {formatDate(r.created_at)}
                        </TableCell>
                        {isPlayer && (
                          <TableCell>
                            <div className="flex gap-1">
                              <Button
                                variant="outline"
                                size="icon"
                                className="h-7 w-7 border-green-500 text-green-600 hover:bg-green-50"
                                onClick={() =>
                                  setDecideTarget({ id: r.id, decision: "accept" })
                                }
                              >
                                <Check className="h-3.5 w-3.5" />
                              </Button>
                              <Button
                                variant="outline"
                                size="icon"
                                className="h-7 w-7 border-red-400 text-red-600 hover:bg-red-50"
                                onClick={() =>
                                  setDecideTarget({ id: r.id, decision: "reject" })
                                }
                              >
                                <X className="h-3.5 w-3.5" />
                              </Button>
                            </div>
                          </TableCell>
                        )}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          )}

          {historical.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">
                History
              </h2>
              <div className="rounded-lg border border-border overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>ID</TableHead>
                      <TableHead>Player</TableHead>
                      <TableHead>Club</TableHead>
                      <TableHead>Season</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Created</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {historical.map((r) => (
                      <TableRow key={r.id} className="hover:bg-muted/50">
                        <TableCell className="text-muted-foreground">#{r.id}</TableCell>
                        <TableCell>Player {r.player_id}</TableCell>
                        <TableCell>Club {r.club_id}</TableCell>
                        <TableCell>Season {r.season_id}</TableCell>
                        <TableCell>
                          <StatusBadge status={r.status} />
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {formatDate(r.created_at)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          )}
        </div>
      )}

      <CreateDialog open={createOpen} onOpenChange={setCreateOpen} />

      {decideTarget && (
        <ConfirmDialog
          open
          onOpenChange={(v) => { if (!v) setDecideTarget(null); }}
          title={decideTarget.decision === "accept" ? "Accept registration?" : "Reject registration?"}
          description={
            decideTarget.decision === "accept"
              ? "You are confirming that you accept this registration request. This will create an active registration for you."
              : "You are rejecting this registration request. The club will be notified."
          }
          confirmLabel={decideTarget.decision === "accept" ? "Accept" : "Reject"}
          destructive={decideTarget.decision === "reject"}
          loading={decideMutation.isPending}
          onConfirm={() => decideMutation.mutate(decideTarget)}
        />
      )}
    </div>
  );
}
