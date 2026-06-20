"use client";

import { useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  AlertCircle,
  ExternalLink,
  FileText,
  Lock,
  Upload,
  UserMinus,
} from "lucide-react";

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
import { releasesApi, playersApi, seasonsApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { PlayerRead, ReleaseRead, SeasonRead, UploadUrlResponse } from "@/types";

// ---------------------------------------------------------------------------
// S3 helper
// ---------------------------------------------------------------------------

async function uploadToS3(uploadUrl: UploadUrlResponse, file: File): Promise<void> {
  const form = new FormData();
  for (const [k, v] of Object.entries(uploadUrl.fields)) {
    form.append(k, v as string);
  }
  form.append("file", file);
  const res = await fetch(uploadUrl.url, { method: "POST", body: form });
  if (!res.ok) throw new Error("Document upload failed — please try again");
}

// ---------------------------------------------------------------------------
// Release dialog — two-step: (1) upload PDF, (2) confirm
// ---------------------------------------------------------------------------

function ReleaseDialog({
  player,
  onClose,
}: {
  player: PlayerRead;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState<"form" | "confirm">("form");
  const [file, setFile] = useState<File | null>(null);
  const [effectiveDate, setEffectiveDate] = useState("");
  const [uploading, setUploading] = useState(false);
  const [fileError, setFileError] = useState(false);

  const releaseMutation = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("A release document PDF is required.");
      setUploading(true);
      const uploadUrl = await releasesApi.documentUploadUrl(
        file.name,
        file.type || "application/pdf"
      );
      await uploadToS3(uploadUrl, file);
      setUploading(false);

      return releasesApi.create({
        player_id: player.id,
        s3_key: uploadUrl.key,
        file_name: file.name,
        effective_date: effectiveDate || undefined,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["players"] });
      queryClient.invalidateQueries({ queryKey: ["releases"] });
      queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
      toast.success(`${player.full_name} released — they are now a free agent`);
      onClose();
    },
    onError: (err: Error) => {
      setUploading(false);
      setStep("form");
      toast.error(err.message);
    },
  });

  const isWorking = releaseMutation.isPending;

  const handleNext = () => {
    if (!file) {
      setFileError(true);
      return;
    }
    setFileError(false);
    setStep("confirm");
  };

  return (
    <Dialog open onOpenChange={(v) => { if (!v && !isWorking) onClose(); }}>
      <DialogContent>
        {step === "form" ? (
          <>
            <DialogHeader>
              <DialogTitle>Release {player.full_name}</DialogTitle>
            </DialogHeader>
            <p className="text-sm text-muted-foreground -mt-2">
              Attach the official release letter. The player will be removed from
              your club and can view this document from their profile.
            </p>

            <div className="space-y-4">
              <div className="space-y-1.5">
                <Label>Release document (PDF) *</Label>
                <div
                  className="flex items-center gap-2 rounded-md border border-border px-3 py-2.5 cursor-pointer hover:bg-muted/50 transition-colors"
                  onClick={() => fileRef.current?.click()}
                >
                  <Upload className="h-4 w-4 text-muted-foreground shrink-0" />
                  <span className="text-sm text-muted-foreground truncate">
                    {file ? file.name : "Click to choose a PDF file…"}
                  </span>
                </div>
                <input
                  ref={fileRef}
                  type="file"
                  accept="application/pdf,.pdf"
                  className="hidden"
                  onChange={(e) => {
                    setFile(e.target.files?.[0] ?? null);
                    setFileError(false);
                  }}
                />
                {fileError && (
                  <p className="text-xs text-destructive flex items-center gap-1">
                    <AlertCircle className="h-3 w-3" /> A release document is required
                  </p>
                )}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="eff-date">Effective date (optional)</Label>
                <Input
                  id="eff-date"
                  type="date"
                  value={effectiveDate}
                  onChange={(e) => setEffectiveDate(e.target.value)}
                />
              </div>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button onClick={handleNext}>
                Continue
              </Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>Are you sure?</DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                You are about to release{" "}
                <span className="font-semibold text-foreground">{player.full_name}</span>{" "}
                from your club. This will:
              </p>
              <ul className="text-sm space-y-1 pl-4">
                <li className="text-muted-foreground">
                  • Remove them from your club immediately
                </li>
                <li className="text-muted-foreground">
                  • Attach the release letter: <span className="font-mono text-xs">{file?.name}</span>
                </li>
                <li className="text-muted-foreground">
                  • If they were a club admin, that role will be revoked
                </li>
              </ul>
              <p className="text-sm font-medium text-destructive">
                This cannot be undone.
              </p>
            </div>

            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setStep("form")}
                disabled={isWorking}
              >
                Back
              </Button>
              <Button
                variant="destructive"
                disabled={isWorking}
                onClick={() => releaseMutation.mutate()}
              >
                {uploading
                  ? "Uploading document…"
                  : isWorking
                  ? "Releasing…"
                  : "Confirm release"}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Club admin view — list club members, release with PDF
// ---------------------------------------------------------------------------

function ClubAdminView({ clubId }: { clubId: number }) {
  const [releaseTarget, setReleaseTarget] = useState<PlayerRead | null>(null);

  const { data: players = [], isLoading: playersLoading } = useQuery<PlayerRead[]>({
    queryKey: ["players"],
    queryFn: playersApi.list,
  });

  const { data: seasons = [] } = useQuery<SeasonRead[]>({
    queryKey: ["seasons"],
    queryFn: seasonsApi.list,
  });

  const seasonLocked = seasons.some((s) => s.status === "active");
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
        <ReleaseDialog
          player={releaseTarget}
          onClose={() => setReleaseTarget(null)}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Player view — own release records from clubs
// ---------------------------------------------------------------------------

function PlayerView({
  playerId,
  releases,
}: {
  playerId: number;
  releases: ReleaseRead[];
}) {
  const mine = releases.filter((r) => r.player_id === playerId);

  if (mine.length === 0) {
    return (
      <EmptyState
        title="No release records"
        description="Release records from your clubs will appear here"
        icon={<FileText className="h-6 w-6" />}
      />
    );
  }

  return (
    <div className="rounded-lg border border-border overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Club</TableHead>
            <TableHead>Effective date</TableHead>
            <TableHead>Documents</TableHead>
            <TableHead>Date</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {mine.map((r) => (
            <TableRow key={r.id}>
              <TableCell className="font-medium">Club {r.from_club_id}</TableCell>
              <TableCell className="text-sm">
                {r.effective_date ? formatDate(r.effective_date) : "—"}
              </TableCell>
              <TableCell>
                <div className="flex flex-col gap-1">
                  {r.documents.map((doc) => (
                    <a
                      key={doc.id}
                      href={doc.file_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-xs text-primary hover:underline"
                    >
                      <FileText className="h-3 w-3" />
                      {doc.file_name}
                      <ExternalLink className="h-2.5 w-2.5" />
                    </a>
                  ))}
                  {r.documents.length === 0 && (
                    <span className="text-xs text-muted-foreground">—</span>
                  )}
                </div>
              </TableCell>
              <TableCell className="text-sm text-muted-foreground">
                {r.confirmed_at ? formatDate(r.confirmed_at) : formatDate(r.created_at)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ReleasesPage() {
  const { user } = useCurrentUser();
  const isPureClubAdmin = user?.role === "club_admin";

  const { data: releases = [], isLoading, error, refetch } = useQuery<ReleaseRead[]>({
    queryKey: ["releases"],
    queryFn: releasesApi.list,
    enabled: !isPureClubAdmin,
  });

  return (
    <div>
      <PageHeader
        title="Releases"
        description={
          isPureClubAdmin
            ? "Release players from your club — a PDF release letter is required"
            : "Release records from your clubs"
        }
      />

      {isPureClubAdmin && user?.club_id ? (
        <ClubAdminView clubId={user.club_id} />
      ) : isLoading ? (
        <DataTableSkeleton columns={4} />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : user?.player_id ? (
        <PlayerView playerId={user.player_id} releases={releases} />
      ) : (
        <EmptyState
          title="No release records"
          description="Release records from your clubs will appear here"
          icon={<FileText className="h-6 w-6" />}
        />
      )}
    </div>
  );
}
