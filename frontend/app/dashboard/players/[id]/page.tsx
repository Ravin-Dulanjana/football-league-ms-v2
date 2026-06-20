"use client";

import { useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Calendar,
  CreditCard,
  ExternalLink,
  FileText,
  Hash,
  Phone,
  Upload,
  AlertCircle,
} from "lucide-react";
import { toast } from "sonner";

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
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ImageLightbox } from "@/components/shared/ImageLightbox";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { playersApi, clubsApi, registrationsApi, releasesApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type {
  ClubRead,
  PlayerDocumentRead,
  PlayerRead,
  RegistrationRequestRead,
  ReleaseRead,
  UploadUrlResponse,
} from "@/types";

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
  if (!res.ok) throw new Error("Upload failed — please try again");
}

// ---------------------------------------------------------------------------
// Upload external document dialog (player self-service)
// ---------------------------------------------------------------------------

function UploadDocumentDialog({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [description, setDescription] = useState("");
  const [fileError, setFileError] = useState(false);
  const [uploading, setUploading] = useState(false);

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!file) {
        setFileError(true);
        throw new Error("Please choose a PDF file.");
      }
      setFileError(false);
      setUploading(true);
      const uploadUrl = await playersApi.myDocumentUploadUrl(
        file.name,
        file.type || "application/pdf"
      );
      await uploadToS3(uploadUrl, file);
      setUploading(false);

      return playersApi.saveMyDocument({
        s3_key: uploadUrl.key,
        file_name: file.name,
        description: description.trim() || undefined,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["player-documents"] });
      toast.success("Document uploaded");
      onClose();
    },
    onError: (err: Error) => {
      setUploading(false);
      toast.error(err.message);
    },
  });

  const isWorking = saveMutation.isPending;

  return (
    <Dialog open onOpenChange={(v) => { if (!v && !isWorking) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Upload external release document</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground -mt-2">
          Upload a release letter from another league or club. Clubs viewing your
          profile can see and download it before inviting you.
        </p>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label>PDF document *</Label>
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
                <AlertCircle className="h-3 w-3" /> A PDF file is required
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="doc-desc">Description (optional)</Label>
            <Input
              id="doc-desc"
              placeholder="e.g. Jaffna FC 2027 release letter"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isWorking}>
            Cancel
          </Button>
          <Button disabled={isWorking} onClick={() => saveMutation.mutate()}>
            {uploading ? "Uploading…" : isWorking ? "Saving…" : "Upload document"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function PlayerDetailPage() {
  const params = useParams();
  const router = useRouter();
  const playerId = Number(params.id);
  const [lightboxSrc, setLightboxSrc] = useState<string | null>(null);
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);

  const { user } = useCurrentUser();
  const isOwnProfile = user?.player_id === playerId;
  // Release docs are only visible to the player themselves, club admins, or league admins.
  const canSeeDocs =
    isOwnProfile ||
    user?.role === "club_admin" ||
    user?.role === "league_admin" ||
    user?.role === "super_admin";

  const { data: player, isLoading } = useQuery<PlayerRead>({
    queryKey: ["player", playerId],
    queryFn: () => playersApi.get(playerId),
  });

  const { data: allRegistrations = [] } = useQuery<RegistrationRequestRead[]>({
    queryKey: ["registrations"],
    queryFn: registrationsApi.list,
    enabled: !!player,
  });

  const { data: allReleases = [] } = useQuery<ReleaseRead[]>({
    queryKey: ["releases"],
    queryFn: releasesApi.list,
    enabled: !!player && canSeeDocs,
  });
  const playerReleases = allReleases.filter(
    (r) => r.player_id === playerId && r.status === "confirmed"
  );

  const { data: playerDocuments = [] } = useQuery<PlayerDocumentRead[]>({
    queryKey: ["player-documents", playerId],
    queryFn: () => playersApi.getDocuments(playerId),
    enabled: !!player && canSeeDocs,
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

  const hasAnyDocs = playerReleases.length > 0 || playerDocuments.length > 0;

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
          <div className="relative shrink-0">
            {player.photo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={player.photo_url}
                alt={player.full_name}
                className="w-20 h-20 rounded-full object-cover ring-2 ring-border cursor-zoom-in"
                onClick={() => setLightboxSrc(player.photo_url!)}
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

        {player.phone_number && (
          <div className="rounded-lg border border-border bg-card p-4 flex items-start gap-3">
            <Phone className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
            <div>
              <p className="text-xs text-muted-foreground">Phone</p>
              <p className="text-sm font-medium mt-0.5">{player.phone_number}</p>
            </div>
          </div>
        )}
      </div>

      {/* Release documents & external docs — only visible to the player, club admins, and league admins */}
      {canSeeDocs && (hasAnyDocs || isOwnProfile) && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Release documents
            </p>
            {isOwnProfile && (
              <Button
                size="sm"
                variant="outline"
                className="h-7 gap-1.5 text-xs"
                onClick={() => setUploadDialogOpen(true)}
              >
                <Upload className="h-3.5 w-3.5" />
                Upload doc
              </Button>
            )}
          </div>

          {!hasAnyDocs && isOwnProfile && (
            <p className="text-sm text-muted-foreground">
              No release documents yet. Upload external release letters so clubs can
              verify your history.
            </p>
          )}

          {/* System release records */}
          {playerReleases.length > 0 && (
            <div className="space-y-2 mb-3">
              {playerReleases.map((release) => (
                <div
                  key={release.id}
                  className="flex items-start justify-between p-4 rounded-lg border border-border bg-card gap-4"
                >
                  <div className="space-y-1 min-w-0">
                    <p className="text-sm font-medium">
                      Released from Club {release.from_club_id}
                    </p>
                    {release.effective_date && (
                      <p className="text-xs text-muted-foreground">
                        Effective: {formatDate(release.effective_date)}
                      </p>
                    )}
                    <p className="text-xs text-muted-foreground">
                      {formatDate(release.confirmed_at ?? release.created_at)}
                    </p>
                  </div>
                  {release.documents.length > 0 && (
                    <div className="flex flex-col gap-1 shrink-0">
                      {release.documents.map((doc) => (
                        <a
                          key={doc.id}
                          href={doc.file_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1.5 text-xs text-primary hover:underline"
                        >
                          <FileText className="h-3 w-3" />
                          {doc.file_name}
                          <ExternalLink className="h-2.5 w-2.5" />
                        </a>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Player-uploaded external docs */}
          {playerDocuments.length > 0 && (
            <div className="space-y-2">
              {playerDocuments.map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-center justify-between p-4 rounded-lg border border-border bg-card gap-4"
                >
                  <div className="space-y-0.5 min-w-0">
                    <a
                      href={doc.file_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
                    >
                      <FileText className="h-3.5 w-3.5 shrink-0" />
                      <span className="truncate">{doc.file_name}</span>
                      <ExternalLink className="h-2.5 w-2.5 shrink-0" />
                    </a>
                    {doc.description && (
                      <p className="text-xs text-muted-foreground pl-5">{doc.description}</p>
                    )}
                    <p className="text-xs text-muted-foreground pl-5">
                      {formatDate(doc.created_at)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

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

      <ImageLightbox
        src={lightboxSrc ?? ""}
        alt="Player photo"
        open={!!lightboxSrc}
        onClose={() => setLightboxSrc(null)}
      />

      {uploadDialogOpen && (
        <UploadDocumentDialog onClose={() => setUploadDialogOpen(false)} />
      )}
    </div>
  );
}
