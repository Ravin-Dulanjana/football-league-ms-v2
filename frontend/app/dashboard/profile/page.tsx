"use client";

import { useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import {
  Building2,
  CalendarDays,
  Camera,
  CheckCircle2,
  ClipboardList,
  CreditCard,
  ExternalLink,
  FileText,
  Mail,
  Pencil,
  Phone,
  Shield,
  Upload,
  User,
  UserPlus,
  XCircle,
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
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { PageHeader } from "@/components/shared/DataTable";
import { ImageLightbox } from "@/components/shared/ImageLightbox";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { clubMembershipsApi, clubsApi, playersApi, registrationsApi } from "@/lib/api";
import { formatRelative } from "@/lib/utils";
import type {
  ClubMembershipRequestRead,
  ClubRead,
  PlayerRead,
  RegistrationRequestRead,
} from "@/types";

// ---------------------------------------------------------------------------
// Edit name dialog
// ---------------------------------------------------------------------------

const editNameSchema = z.object({
  full_name: z.string().min(1, "Name is required"),
});

type EditNameForm = z.infer<typeof editNameSchema>;

function EditNameDialog({
  playerId,
  currentName,
  open,
  onOpenChange,
}: {
  playerId: number;
  currentName: string;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const queryClient = useQueryClient();

  const form = useForm<EditNameForm>({
    resolver: zodResolver(editNameSchema),
    defaultValues: { full_name: currentName },
  });

  const mutation = useMutation({
    mutationFn: (data: EditNameForm) =>
      playersApi.update(playerId, { full_name: data.full_name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["player", playerId] });
      queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
      toast.success("Name updated");
      onOpenChange(false);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit your name</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={form.handleSubmit((d) => mutation.mutate(d))}
          className="space-y-4"
        >
          <div className="space-y-1.5">
            <Label htmlFor="pf-name">Full name *</Label>
            <Input id="pf-name" {...form.register("full_name")} />
            {form.formState.errors.full_name && (
              <p className="text-xs text-destructive">
                {form.formState.errors.full_name.message}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Photo upload
// ---------------------------------------------------------------------------

function PhotoUploadButton({
  playerId,
  currentPhotoUrl,
}: {
  playerId: number;
  currentPhotoUrl: string | null;
}) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [lightboxOpen, setLightboxOpen] = useState(false);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const { url, fields, key } = await playersApi.myPhotoUploadUrl(
        file.name,
        file.type || "image/jpeg"
      );
      const formData = new FormData();
      Object.entries(fields).forEach(([k, v]) => formData.append(k, v));
      formData.append("file", file);
      const s3Res = await fetch(url, { method: "POST", body: formData });
      if (!s3Res.ok) throw new Error("Upload to S3 failed");
      await playersApi.update(playerId, { photo_key: key });
      queryClient.invalidateQueries({ queryKey: ["player", playerId] });
      toast.success("Profile photo updated");
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <div className="relative">
      <div className="w-20 h-20 rounded-full bg-primary/10 text-primary flex items-center justify-center text-2xl font-bold overflow-hidden">
        {currentPhotoUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={currentPhotoUrl}
            alt="Profile"
            className="w-full h-full object-cover cursor-zoom-in"
            onClick={() => setLightboxOpen(true)}
          />
        ) : (
          <User className="h-8 w-8" />
        )}
      </div>
      <button
        onClick={() => fileInputRef.current?.click()}
        disabled={uploading}
        className="absolute -bottom-1 -right-1 w-7 h-7 rounded-full bg-primary text-primary-foreground flex items-center justify-center hover:opacity-90 transition-opacity disabled:opacity-50"
        title="Change photo"
      >
        {uploading ? (
          <span className="text-xs">…</span>
        ) : (
          <Camera className="h-3.5 w-3.5" />
        )}
      </button>
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={handleFileChange}
      />
      {currentPhotoUrl && (
        <ImageLightbox
          src={currentPhotoUrl}
          alt="Profile photo"
          open={lightboxOpen}
          onClose={() => setLightboxOpen(false)}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// NIC document upload
// ---------------------------------------------------------------------------

function NicDocumentSection({
  playerId,
  currentNicDocUrl,
}: {
  playerId: number;
  currentNicDocUrl: string | null;
}) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.type !== "application/pdf") {
      toast.error("Only PDF files are accepted");
      return;
    }
    setUploading(true);
    try {
      const { url, fields, key } = await playersApi.myNicUploadUrl(file.name, "application/pdf");
      const formData = new FormData();
      Object.entries(fields).forEach(([k, v]) => formData.append(k, v));
      formData.append("file", file);
      const s3Res = await fetch(url, { method: "POST", body: formData });
      if (!s3Res.ok) throw new Error("Upload to S3 failed");
      await playersApi.saveMyNicDocument({ nic_document_key: key });
      queryClient.invalidateQueries({ queryKey: ["player", playerId] });
      toast.success("NIC document uploaded");
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <p className="text-xs text-muted-foreground mb-3 flex items-center gap-1.5">
        <FileText className="h-3 w-3" />
        NIC Document (PDF)
      </p>
      <div className="flex items-center gap-2">
        {currentNicDocUrl ? (
          <>
            <a
              href={currentNicDocUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-xs text-primary hover:underline"
            >
              <ExternalLink className="h-3 w-3" />
              View document
            </a>
            <span className="text-muted-foreground text-xs">·</span>
          </>
        ) : (
          <p className="text-xs text-muted-foreground flex-1">No document uploaded yet</p>
        )}
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
        >
          <Upload className="h-3 w-3" />
          {uploading ? "Uploading…" : currentNicDocUrl ? "Replace" : "Upload PDF"}
        </button>
      </div>
      <input
        ref={fileInputRef}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={handleFileChange}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Club Invites section (for users without a club)
// ---------------------------------------------------------------------------

function ClubInvitesSection() {
  const queryClient = useQueryClient();

  const { data: requests = [], isLoading } = useQuery<ClubMembershipRequestRead[]>({
    queryKey: ["club-memberships", "requests"],
    queryFn: clubMembershipsApi.listRequests,
  });

  const { data: clubs } = useQuery<ClubRead[]>({
    queryKey: ["clubs"],
    queryFn: clubsApi.list,
  });
  const clubMap = Object.fromEntries((clubs ?? []).map((c) => [c.id, c.name]));

  const decideMutation = useMutation({
    mutationFn: ({ id, decision }: { id: number; decision: "accept" | "reject" }) =>
      clubMembershipsApi.decide(id, { decision }),
    onSuccess: (_, { decision }) => {
      queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
      queryClient.invalidateQueries({ queryKey: ["club-memberships"] });
      queryClient.invalidateQueries({ queryKey: ["players"] });
      if (decision === "accept") {
        toast.success("You've joined the club! Welcome to the squad.");
        window.location.assign("/dashboard/profile");
      } else {
        toast.success("Invite declined");
      }
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const pending = requests.filter((r) => r.status === "pending");
  const past = requests.filter((r) => r.status !== "pending");

  if (isLoading) return null;

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Club Invites
        </p>
        {pending.length > 0 && (
          <span className="text-[10px] font-bold bg-primary text-white px-1.5 py-0.5 rounded-full">
            {pending.length}
          </span>
        )}
      </div>

      {requests.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border p-5 text-center">
          <UserPlus className="h-5 w-5 text-muted-foreground mx-auto mb-2" />
          <p className="text-sm text-muted-foreground">No club invites yet</p>
          <p className="text-xs text-muted-foreground mt-1">
            A club admin can invite you to join their club
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {pending.length > 0 && (
            <div className="rounded-xl border border-border bg-card overflow-hidden">
              <div className="px-4 py-2.5 border-b border-border bg-muted/30">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                  Pending ({pending.length})
                </p>
              </div>
              <div className="divide-y divide-border">
                {pending.map((req) => (
                  <div key={req.id} className="flex items-center justify-between px-4 py-3">
                    <div>
                      <p className="text-sm font-medium">
                        {clubMap[req.club_id] ?? `Club #${req.club_id}`}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Sent {formatRelative(req.created_at)}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        className="h-7 text-xs gap-1"
                        onClick={() => decideMutation.mutate({ id: req.id, decision: "accept" })}
                        disabled={decideMutation.isPending}
                      >
                        <CheckCircle2 className="h-3 w-3" />
                        Accept
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 text-xs text-muted-foreground hover:text-destructive gap-1"
                        onClick={() => decideMutation.mutate({ id: req.id, decision: "reject" })}
                        disabled={decideMutation.isPending}
                      >
                        <XCircle className="h-3 w-3" />
                        Decline
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {past.length > 0 && (
            <div className="rounded-xl border border-border bg-card overflow-hidden">
              <div className="px-4 py-2.5 border-b border-border bg-muted/30">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                  History
                </p>
              </div>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Club</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Responded</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {past.map((req) => (
                    <TableRow key={req.id}>
                      <TableCell className="text-sm font-medium">
                        {clubMap[req.club_id] ?? `Club #${req.club_id}`}
                      </TableCell>
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
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// My Registrations section (for users who are in a club)
// ---------------------------------------------------------------------------

function MyRegistrationsSection({ playerId }: { playerId: number }) {
  const queryClient = useQueryClient();

  const { data: requests = [], isLoading } = useQuery<RegistrationRequestRead[]>({
    queryKey: ["registrations"],
    queryFn: registrationsApi.list,
  });

  const myRequests = requests.filter((r) => r.player_id === playerId);
  const pending = myRequests.filter((r) => r.status === "pending_player_confirmation");
  const past = myRequests.filter((r) => r.status !== "pending_player_confirmation");

  const decideMutation = useMutation({
    mutationFn: (id: number) => registrationsApi.decide(id, "accept"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["registrations"] });
      toast.success("Registration confirmed — you are now registered for this season");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  if (isLoading) return null;

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Season Registrations
        </p>
        {pending.length > 0 && (
          <span className="text-[10px] font-bold bg-primary text-white px-1.5 py-0.5 rounded-full">
            {pending.length}
          </span>
        )}
      </div>

      {myRequests.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border p-5 text-center">
          <ClipboardList className="h-5 w-5 text-muted-foreground mx-auto mb-2" />
          <p className="text-sm text-muted-foreground">No season registration requests yet</p>
          <p className="text-xs text-muted-foreground mt-1">
            Your club admin will send you a request to join the season squad
          </p>
        </div>
      ) : (
        <div className="rounded-xl border border-border bg-card overflow-hidden">
          {pending.length > 0 && (
            <>
              <div className="px-4 py-2.5 border-b border-border bg-muted/30">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                  Pending acknowledgement ({pending.length})
                </p>
              </div>
              <div className="divide-y divide-border">
                {pending.map((req) => (
                  <div key={req.id} className="flex items-center justify-between px-4 py-3">
                    <div>
                      <p className="text-sm font-medium">Season registration request</p>
                      <p className="text-xs text-muted-foreground">
                        Season #{req.season_id} · {formatRelative(req.created_at)}
                      </p>
                    </div>
                    <Button
                      size="sm"
                      className="h-7 text-xs gap-1"
                      onClick={() => decideMutation.mutate(req.id)}
                      disabled={decideMutation.isPending}
                    >
                      <CheckCircle2 className="h-3 w-3" />
                      Acknowledge
                    </Button>
                  </div>
                ))}
              </div>
            </>
          )}
          {past.length > 0 && (
            <>
              <div className="px-4 py-2.5 border-b border-border bg-muted/30">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                  History
                </p>
              </div>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Season</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Date</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {past.map((req) => (
                    <TableRow key={req.id}>
                      <TableCell className="text-sm">Season #{req.season_id}</TableCell>
                      <TableCell>
                        <StatusBadge status={req.status} />
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatRelative(req.created_at)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main profile page
// ---------------------------------------------------------------------------

export default function ProfilePage() {
  const [editNameOpen, setEditNameOpen] = useState(false);
  const queryClient = useQueryClient();
  const { user, isLoading: userLoading, isSuperAdmin } = useCurrentUser();

  const hasClub = !!user?.club_id;

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

  if (userLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="flex items-center gap-5">
          <Skeleton className="w-20 h-20 rounded-full" />
          <div className="space-y-2">
            <Skeleton className="h-6 w-40" />
            <Skeleton className="h-4 w-56" />
          </div>
        </div>
      </div>
    );
  }

  if (!user) return null;

  const govRoles = user.governance_roles ?? [];
  const displayName = player?.full_name ?? user.email.split("@")[0];

  return (
    <div className="space-y-6 max-w-2xl">
      <PageHeader
        title="My Profile"
        description="Your account information and identity"
      />

      {/* Identity card */}
      <div className="rounded-xl border border-border bg-card p-6">
        <div className="flex items-start gap-5">
          {/* Avatar */}
          {user.player_id ? (
            <PhotoUploadButton
              playerId={user.player_id}
              currentPhotoUrl={player?.photo_url ?? null}
            />
          ) : (
            <div className="w-20 h-20 rounded-full bg-primary/10 text-primary flex items-center justify-center text-2xl font-bold shrink-0">
              {user.email[0].toUpperCase()}
            </div>
          )}

          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <div>
                <h2 className="text-xl font-semibold">{displayName}</h2>
                <a
                  href={`mailto:${user.email}`}
                  className="flex items-center gap-1.5 text-sm text-muted-foreground mt-0.5 hover:text-primary transition-colors"
                >
                  <Mail className="h-3.5 w-3.5" />
                  {user.email}
                </a>
              </div>
              {user.player_id && player && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setEditNameOpen(true)}
                  className="gap-1.5 shrink-0"
                >
                  <Pencil className="h-3.5 w-3.5" />
                  Edit name
                </Button>
              )}
            </div>

            {/* Role badges */}
            <div className="flex items-center gap-1.5 flex-wrap mt-3">
              {user.member_type && <StatusBadge status={user.member_type} />}
              {govRoles.map((gr, i) => (
                <StatusBadge key={`${gr.role}-${i}`} status={gr.role} />
              ))}
              {!user.member_type && govRoles.length === 0 && (
                <StatusBadge status={user.role} />
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Club affiliation */}
      {club && (
        <div>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">
            Club
          </p>
          <button
            onClick={() => window.location.assign(`/dashboard/clubs/${club.id}`)}
            className="flex items-center gap-4 p-4 rounded-xl border border-border bg-card hover:bg-muted/50 transition-colors w-full text-left"
          >
            <div className="w-12 h-12 rounded-lg bg-primary/10 text-primary font-bold flex items-center justify-center text-sm shrink-0">
              {club.logo_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={club.logo_url}
                  alt={club.name}
                  className="w-full h-full rounded-lg object-cover"
                />
              ) : (
                <Building2 className="h-5 w-5" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-medium">{club.name}</p>
              <p className="text-xs text-muted-foreground">
                {club.short_name ?? club.code}
                {club.established_year && ` · Est. ${club.established_year}`}
              </p>
            </div>
            <StatusBadge status={club.status} />
          </button>
        </div>
      )}

      {/* Player identity details */}
      {player && (
        <div>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">
            My Details
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="rounded-lg border border-border bg-card p-4">
              <p className="text-xs text-muted-foreground mb-1 flex items-center gap-1.5">
                <CalendarDays className="h-3 w-3" />
                Date of birth
              </p>
              <p className="text-sm font-medium">{player.date_of_birth}</p>
            </div>
            <div className="rounded-lg border border-border bg-card p-4">
              <p className="text-xs text-muted-foreground mb-1 flex items-center gap-1.5">
                <CreditCard className="h-3 w-3" />
                NIC number
              </p>
              <p className="text-sm font-mono font-medium">{player.nic_number}</p>
            </div>
            {player.phone_number && (
              <div className="rounded-lg border border-border bg-card p-4">
                <p className="text-xs text-muted-foreground mb-1 flex items-center gap-1.5">
                  <Phone className="h-3 w-3" />
                  Phone
                </p>
                <p className="text-sm font-medium">{player.phone_number}</p>
              </div>
            )}
            <div className="rounded-lg border border-border bg-card p-4">
              <p className="text-xs text-muted-foreground mb-1 flex items-center gap-1.5">
                <Shield className="h-3 w-3" />
                Player code
              </p>
              <p className="text-sm font-mono font-medium">{player.league_player_code}</p>
            </div>
            {user.player_id && (
              <NicDocumentSection
                playerId={user.player_id}
                currentNicDocUrl={player.nic_document_url ?? null}
              />
            )}
          </div>
        </div>
      )}

      {/* No player profile */}
      {!user.player_id && (
        <div className="rounded-lg border border-dashed border-border p-6 text-center">
          <User className="h-6 w-6 text-muted-foreground mx-auto mb-2" />
          <p className="text-sm text-muted-foreground">
            No player profile linked to your account
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            Contact a league admin to link your identity
          </p>
        </div>
      )}

      {/* Club invites (users without a club) or Season registrations (users with a club) */}
      {!isSuperAdmin && user.player_id && (
        !hasClub
          ? <ClubInvitesSection />
          : <MyRegistrationsSection playerId={user.player_id} />
      )}

      {/* Edit name dialog */}
      {user.player_id && player && (
        <EditNameDialog
          playerId={user.player_id}
          currentName={player.full_name}
          open={editNameOpen}
          onOpenChange={(v) => {
            setEditNameOpen(v);
            if (!v) queryClient.invalidateQueries({ queryKey: ["player", user.player_id] });
          }}
        />
      )}
    </div>
  );
}
