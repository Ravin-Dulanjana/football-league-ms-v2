"use client";

import { useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { CheckCheck, ExternalLink, FileText, Paperclip, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
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
import { releasesApi, registrationsApi, playersApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type {
  PlayerRead,
  PlayerSeasonRegistrationRead,
  ReleaseRead,
} from "@/types";

// ---------------------------------------------------------------------------
// Create release dialog — club admin only
// ---------------------------------------------------------------------------

const createSchema = z.object({
  registration_id: z.number().int().positive("Select a player"),
  effective_date: z.string().optional(),
});
type CreateForm = z.infer<typeof createSchema>;

function CreateReleaseDialog({
  clubId,
  open,
  onOpenChange,
}: {
  clubId: number;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  const { data: activeRegs = [] } = useQuery<PlayerSeasonRegistrationRead[]>({
    queryKey: ["player-season-registrations", clubId],
    queryFn: () => registrationsApi.listPlayerSeasonRegistrations({ club_id: clubId }),
    enabled: open,
  });

  const { data: players = [] } = useQuery<PlayerRead[]>({
    queryKey: ["players"],
    queryFn: playersApi.list,
    enabled: open,
  });
  const playerMap = new Map(players.map((p) => [p.id, p]));

  const form = useForm<CreateForm>({
    resolver: zodResolver(createSchema),
    defaultValues: { registration_id: 0, effective_date: "" },
  });

  const mutation = useMutation({
    mutationFn: async (data: CreateForm) => {
      if (!selectedFile) throw new Error("Please attach a release document (PDF)");

      setUploading(true);
      try {
        // Step 1: get pre-signed URL
        const { url, fields, key } = await releasesApi.documentUploadUrl(
          selectedFile.name,
          selectedFile.type || "application/pdf"
        );

        // Step 2: upload directly to S3
        const formData = new FormData();
        for (const [k, v] of Object.entries(fields)) {
          formData.append(k, v);
        }
        formData.append("file", selectedFile);
        const s3Res = await fetch(url, { method: "POST", body: formData });
        if (!s3Res.ok) throw new Error("Document upload failed — please try again");

        // Step 3: create the release with the s3_key
        return releasesApi.create({
          registration_id: data.registration_id,
          s3_key: key,
          file_name: selectedFile.name,
          effective_date: data.effective_date || undefined,
        });
      } finally {
        setUploading(false);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["releases"] });
      toast.success("Release initiated — player has been notified");
      onOpenChange(false);
      form.reset();
      setSelectedFile(null);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const isWorking = mutation.isPending || uploading;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Release player</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground -mt-2">
          The player will be notified and must acknowledge the release.
          You can only release players from a submitted squad.
        </p>
        <form
          onSubmit={form.handleSubmit((d) => mutation.mutate(d))}
          className="space-y-4"
        >
          <div className="space-y-1.5">
            <Label>Player *</Label>
            <Controller
              control={form.control}
              name="registration_id"
              render={({ field }) => (
                <Select
                  onValueChange={(v) => field.onChange(Number(v))}
                  value={field.value ? String(field.value) : ""}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select player" />
                  </SelectTrigger>
                  <SelectContent>
                    {activeRegs.map((reg) => {
                      const player = playerMap.get(reg.player_id);
                      return (
                        <SelectItem key={reg.id} value={String(reg.id)}>
                          {player?.full_name ?? `Player ${reg.player_id}`}
                          {player && (
                            <span className="ml-1.5 text-muted-foreground font-mono text-xs">
                              {player.league_player_code}
                            </span>
                          )}
                        </SelectItem>
                      );
                    })}
                  </SelectContent>
                </Select>
              )}
            />
            {form.formState.errors.registration_id && (
              <p className="text-xs text-destructive">
                {form.formState.errors.registration_id.message}
              </p>
            )}
            {activeRegs.length === 0 && (
              <p className="text-xs text-muted-foreground">
                No active players found for your club.
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label>Release document (PDF) *</Label>
            <div
              className="flex items-center gap-2 p-3 rounded-lg border border-dashed border-border cursor-pointer hover:bg-muted/40 transition-colors"
              onClick={() => fileRef.current?.click()}
            >
              <Paperclip className="h-4 w-4 text-muted-foreground shrink-0" />
              <span className="text-sm text-muted-foreground truncate">
                {selectedFile ? selectedFile.name : "Click to attach PDF"}
              </span>
            </div>
            <input
              ref={fileRef}
              type="file"
              accept="application/pdf,.pdf"
              className="hidden"
              onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="eff-date">Effective date</Label>
            <Input id="eff-date" type="date" {...form.register("effective_date")} />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isWorking}>
              {isWorking ? (uploading ? "Uploading…" : "Creating…") : "Release player"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Club admin view — sent releases
// ---------------------------------------------------------------------------

function ClubAdminView({
  clubId,
  releases,
  playerMap,
}: {
  clubId: number;
  releases: ReleaseRead[];
  playerMap: Map<number, PlayerRead>;
}) {
  const [createOpen, setCreateOpen] = useState(false);
  const mine = releases.filter((r) => r.from_club_id === clubId);
  const pending = mine.filter((r) => r.status === "pending_player_confirmation");
  const history = mine.filter((r) => r.status !== "pending_player_confirmation");

  return (
    <div className="space-y-6">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setCreateOpen(true)} className="gap-1.5">
          <Plus className="h-4 w-4" />
          Release player
        </Button>
      </div>

      {mine.length === 0 ? (
        <EmptyState
          title="No releases sent"
          description="Submit your squad list first, then you can release players"
          icon={<FileText className="h-6 w-6" />}
          action={{ label: "Release player", onClick: () => setCreateOpen(true) }}
        />
      ) : (
        <>
          {pending.length > 0 && (
            <ReleasesTable
              title={`Awaiting acknowledgement (${pending.length})`}
              rows={pending}
              playerMap={playerMap}
            />
          )}
          {history.length > 0 && (
            <ReleasesTable title="History" rows={history} playerMap={playerMap} />
          )}
        </>
      )}

      <CreateReleaseDialog clubId={clubId} open={createOpen} onOpenChange={setCreateOpen} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Player view — incoming releases with Acknowledge button
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
        <ReleasesTable title="History" rows={history} playerMap={playerMap} />
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
// Shared table
// ---------------------------------------------------------------------------

function ReleasesTable({
  title,
  rows,
  playerMap,
}: {
  title: string;
  rows: ReleaseRead[];
  playerMap: Map<number, PlayerRead>;
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
              <TableHead>Player</TableHead>
              <TableHead>Club</TableHead>
              <TableHead>Effective date</TableHead>
              <TableHead>Document</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Date</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r) => {
              const player = playerMap.get(r.player_id);
              return (
                <TableRow key={r.id} className="hover:bg-muted/50">
                  <TableCell className="font-medium">
                    {player?.full_name ?? `Player ${r.player_id}`}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    Club {r.from_club_id}
                  </TableCell>
                  <TableCell className="text-sm">
                    {r.effective_date ? formatDate(r.effective_date) : "—"}
                  </TableCell>
                  <TableCell>
                    {r.documents.length > 0 ? (
                      <a
                        href={r.documents[0].file_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 text-xs text-primary hover:underline"
                      >
                        <FileText className="h-3 w-3" />
                        {r.documents[0].file_name}
                      </a>
                    ) : (
                      <span className="text-muted-foreground text-xs">—</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={r.status} />
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {r.confirmed_at ? formatDate(r.confirmed_at) : formatDate(r.created_at)}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ReleasesPage() {
  const { user, isClubAdmin, isPlayer } = useCurrentUser();

  const { data: releases = [], isLoading, error, refetch } = useQuery<ReleaseRead[]>({
    queryKey: ["releases"],
    queryFn: releasesApi.list,
  });

  const { data: players = [] } = useQuery<PlayerRead[]>({
    queryKey: ["players"],
    queryFn: playersApi.list,
  });
  const playerMap = new Map(players.map((p) => [p.id, p]));

  return (
    <div>
      <PageHeader
        title="Releases"
        description={
          isClubAdmin
            ? "Release players from your club. Squad must be submitted first."
            : "Release notices from your club"
        }
      />

      {isLoading ? (
        <DataTableSkeleton columns={6} />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : isClubAdmin && user?.club_id ? (
        <ClubAdminView
          clubId={user.club_id}
          releases={releases}
          playerMap={playerMap}
        />
      ) : isPlayer && user?.player_id ? (
        <PlayerView
          playerId={user.player_id}
          releases={releases}
          playerMap={playerMap}
        />
      ) : (
        <EmptyState
          title="No access"
          description="This page is for club admins and players"
          icon={<FileText className="h-6 w-6" />}
        />
      )}
    </div>
  );
}
