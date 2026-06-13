"use client";

import { useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import {
  ArrowLeft,
  Building2,
  Camera,
  CheckCircle2,
  ClipboardCheck,
  ImageIcon,
  Mail,
  Pencil,
  Phone,
  Plus,
  Shield,
  Shirt,
  Trash2,
  UserSquare2,
  Users,
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  ConfirmDialog,
} from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import {
  clubsApi,
  staffApi,
  usersApi,
  registrationsApi,
  playersApi,
  seasonsApi,
  profilesApi,
} from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type {
  ClubRead,
  ClubSeasonProfileRead,
  ClubStaffRead,
  ClubUpdate,
  PlayerRead,
  PlayerSeasonRegistrationRead,
  RegistrationRequestRead,
  SeasonRead,
  UserRead,
} from "@/types";

// ---------------------------------------------------------------------------
// Segment navigation
// ---------------------------------------------------------------------------

type Segment = "overview" | "players" | "staff" | "admins" | "squad";

const SEGMENTS: { id: Segment; label: string; icon: React.ElementType }[] = [
  { id: "overview", label: "Overview", icon: Building2 },
  { id: "players", label: "Players", icon: Shirt },
  { id: "staff", label: "Support Staff", icon: UserSquare2 },
  { id: "admins", label: "Admins", icon: Shield },
  { id: "squad", label: "Season Squad", icon: ClipboardCheck },
];

// ---------------------------------------------------------------------------
// Edit club dialog
// ---------------------------------------------------------------------------

const editClubSchema = z.object({
  name: z.string().min(1, "Required"),
  short_name: z.string().optional(),
  code: z.string().min(2).max(10),
  email: z.string().email("Invalid email").optional().or(z.literal("")),
  phone_number: z.string().optional().or(z.literal("")),
  established_year: z
    .string()
    .optional()
    .refine(
      (v) => !v || (/^\d{4}$/.test(v) && Number(v) >= 1800 && Number(v) <= 2100),
      "Must be a valid 4-digit year"
    ),
  president_name: z.string().optional().or(z.literal("")),
  secretary_name: z.string().optional().or(z.literal("")),
  treasurer_name: z.string().optional().or(z.literal("")),
});

type EditClubForm = z.infer<typeof editClubSchema>;

function EditClubDialog({
  club,
  open,
  onOpenChange,
}: {
  club: ClubRead;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const logoInputRef = useRef<HTMLInputElement>(null);
  const [logoUploading, setLogoUploading] = useState(false);
  const [logoPreview, setLogoPreview] = useState<string | null>(club.logo_url ?? null);

  const handleLogoChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLogoUploading(true);
    try {
      const { url, fields, key } = await clubsApi.logoUploadUrl(
        club.id,
        file.name,
        file.type || "image/jpeg"
      );
      const formData = new FormData();
      Object.entries(fields).forEach(([k, v]) => formData.append(k, v));
      formData.append("file", file);
      const s3Res = await fetch(url, { method: "POST", body: formData });
      if (!s3Res.ok) throw new Error("Upload to S3 failed");
      await clubsApi.update(club.id, { logo_key: key });
      queryClient.invalidateQueries({ queryKey: ["club", club.id] });
      queryClient.invalidateQueries({ queryKey: ["clubs"] });
      setLogoPreview(URL.createObjectURL(file));
      toast.success("Club logo updated");
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setLogoUploading(false);
      if (logoInputRef.current) logoInputRef.current.value = "";
    }
  };

  const form = useForm<EditClubForm>({
    resolver: zodResolver(editClubSchema),
    defaultValues: {
      name: club.name,
      short_name: club.short_name ?? "",
      code: club.code,
      email: club.email ?? "",
      phone_number: club.phone_number ?? "",
      established_year: club.established_year ? String(club.established_year) : "",
      president_name: club.president_name ?? "",
      secretary_name: club.secretary_name ?? "",
      treasurer_name: club.treasurer_name ?? "",
    },
  });

  const mutation = useMutation({
    mutationFn: (data: EditClubForm) => {
      const payload: ClubUpdate = {
        name: data.name,
        short_name: data.short_name || undefined,
        code: data.code.toUpperCase(),
        email: data.email || undefined,
        phone_number: data.phone_number || undefined,
        established_year: data.established_year ? Number(data.established_year) : null,
        president_name: data.president_name || null,
        secretary_name: data.secretary_name || null,
        treasurer_name: data.treasurer_name || null,
      };
      return clubsApi.update(club.id, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["club", club.id] });
      queryClient.invalidateQueries({ queryKey: ["clubs"] });
      toast.success("Club updated");
      onOpenChange(false);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Edit club details</DialogTitle>
        </DialogHeader>
        {/* Logo upload — outside the main form so it doesn't require saving */}
        <div className="flex items-center gap-4 pb-2 border-b border-border">
          <div className="relative">
            <div className="w-16 h-16 rounded-full bg-primary/10 text-primary flex items-center justify-center text-2xl font-bold overflow-hidden border border-border">
              {logoPreview ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={logoPreview} alt={club.name} className="w-full h-full object-cover" />
              ) : (
                <span>{club.name.charAt(0)}</span>
              )}
            </div>
            <button
              type="button"
              onClick={() => logoInputRef.current?.click()}
              disabled={logoUploading}
              className="absolute -bottom-1 -right-1 w-6 h-6 rounded-full bg-primary text-primary-foreground flex items-center justify-center hover:opacity-90 disabled:opacity-50"
              title="Change logo"
            >
              {logoUploading ? <span className="text-[10px]">…</span> : <Camera className="h-3 w-3" />}
            </button>
            <input
              ref={logoInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={handleLogoChange}
            />
          </div>
          <div>
            <p className="text-sm font-medium">Club logo</p>
            <p className="text-xs text-muted-foreground">Click the camera icon to upload</p>
          </div>
        </div>

        <form
          onSubmit={form.handleSubmit((d) => mutation.mutate(d))}
          className="space-y-4"
        >
          <div className="space-y-1.5">
            <Label htmlFor="ec-name">Club name *</Label>
            <Input id="ec-name" {...form.register("name")} />
            {form.formState.errors.name && (
              <p className="text-xs text-destructive">{form.formState.errors.name.message}</p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="ec-short">Short name</Label>
              <Input id="ec-short" {...form.register("short_name")} placeholder="e.g. CFC" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ec-code">Code *</Label>
              <Input
                id="ec-code"
                {...form.register("code")}
                className="uppercase"
                style={{ textTransform: "uppercase" }}
              />
              {form.formState.errors.code && (
                <p className="text-xs text-destructive">{form.formState.errors.code.message}</p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="ec-email">Contact email</Label>
              <Input id="ec-email" type="email" {...form.register("email")} />
              {form.formState.errors.email && (
                <p className="text-xs text-destructive">{form.formState.errors.email.message}</p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ec-phone">Phone number</Label>
              <Input id="ec-phone" {...form.register("phone_number")} placeholder="+94 77 000 0000" />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ec-year">Established year</Label>
            <Input id="ec-year" {...form.register("established_year")} placeholder="e.g. 1987" />
            {form.formState.errors.established_year && (
              <p className="text-xs text-destructive">
                {form.formState.errors.established_year.message}
              </p>
            )}
          </div>

          <div className="border-t border-border pt-3 space-y-3">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Club Officials
            </p>
            <div className="space-y-1.5">
              <Label htmlFor="ec-president">President</Label>
              <Input id="ec-president" {...form.register("president_name")} placeholder="Full name" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ec-secretary">Secretary</Label>
              <Input id="ec-secretary" {...form.register("secretary_name")} placeholder="Full name" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ec-treasurer">Treasurer</Label>
              <Input id="ec-treasurer" {...form.register("treasurer_name")} placeholder="Full name" />
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Saving…" : "Save changes"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Add staff dialog (club_admin only, club fixed to their own)
// ---------------------------------------------------------------------------

const staffSchema = z.object({
  season_id: z.number().int().positive("Select a season"),
  full_name: z.string().min(1, "Required"),
  role: z.string().min(1, "Required"),
});

type StaffForm = z.infer<typeof staffSchema>;

function AddStaffDialog({
  clubId,
  open,
  onOpenChange,
}: {
  clubId: number;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const { data: seasons } = useQuery<SeasonRead[]>({
    queryKey: ["seasons"],
    queryFn: seasonsApi.list,
    enabled: open,
  });

  const form = useForm<StaffForm>({
    resolver: zodResolver(staffSchema),
    defaultValues: { season_id: 0, full_name: "", role: "" },
  });

  const mutation = useMutation({
    mutationFn: (data: StaffForm) =>
      staffApi.create({
        club_id: clubId,
        season_id: data.season_id,
        full_name: data.full_name,
        role: data.role,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["club-staff", clubId] });
      toast.success("Staff member added");
      onOpenChange(false);
      form.reset();
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add support staff</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={form.handleSubmit((d) => mutation.mutate(d))}
          className="space-y-4"
        >
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
                        {s.name}
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
          <div className="space-y-1.5">
            <Label htmlFor="sf-name">Full name *</Label>
            <Input id="sf-name" {...form.register("full_name")} placeholder="e.g. Nimal Perera" />
            {form.formState.errors.full_name && (
              <p className="text-xs text-destructive">
                {form.formState.errors.full_name.message}
              </p>
            )}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="sf-role">Role *</Label>
            <Input id="sf-role" {...form.register("role")} placeholder="e.g. Head Coach" />
            {form.formState.errors.role && (
              <p className="text-xs text-destructive">
                {form.formState.errors.role.message}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Adding…" : "Add staff"}
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

export default function ClubDetailPage() {
  const params = useParams();
  const router = useRouter();
  const clubId = Number(params.id);
  const [segment, setSegment] = useState<Segment>("overview");
  const [addStaffOpen, setAddStaffOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteStaffTarget, setDeleteStaffTarget] = useState<ClubStaffRead | null>(null);
  const coverInputRef = useRef<HTMLInputElement>(null);
  const [coverUploading, setCoverUploading] = useState(false);
  const queryClient = useQueryClient();
  const { user, isSuperAdmin } = useCurrentUser();

  // A user can edit this club only if they have a club_admin governance role
  // for this specific club. League admin alone does NOT grant club editing rights.
  // Super admin can always edit.
  const isOwnClubAdmin = (user?.governance_roles ?? []).some(
    (gr) => gr.role === "club_admin" && gr.club_id === clubId
  );
  const canEdit = isOwnClubAdmin || isSuperAdmin;

  const { data: club, isLoading: clubLoading } = useQuery<ClubRead>({
    queryKey: ["club", clubId],
    queryFn: () => clubsApi.get(clubId),
  });

  const { data: staff = [] } = useQuery<ClubStaffRead[]>({
    queryKey: ["club-staff", clubId],
    queryFn: () => staffApi.list(clubId),
    enabled: segment === "staff",
  });

  const { data: allUsers = [] } = useQuery<UserRead[]>({
    queryKey: ["users"],
    queryFn: () => usersApi.list(),
    enabled: segment === "admins",
  });

  // Season / Squad segment
  const { data: seasons = [] } = useQuery<SeasonRead[]>({
    queryKey: ["seasons"],
    queryFn: seasonsApi.list,
    enabled: segment === "squad",
  });
  const currentSeason = seasons.find((s) => s.status === "open") ?? seasons[seasons.length - 1];

  const { data: profiles = [] } = useQuery<ClubSeasonProfileRead[]>({
    queryKey: ["profiles"],
    queryFn: profilesApi.list,
    enabled: segment === "squad",
  });
  const currentProfile = profiles.find(
    (p) => p.club_id === clubId && p.season_id === (currentSeason?.id ?? -1)
  );

  const { data: squadRegistrations = [] } = useQuery<PlayerSeasonRegistrationRead[]>({
    queryKey: ["player-season-registrations", clubId, currentSeason?.id],
    queryFn: () =>
      registrationsApi.listPlayerSeasonRegistrations({
        club_id: clubId,
        season_id: currentSeason?.id,
      }),
    enabled: segment === "squad" && !!currentSeason,
  });

  const { data: squadStaff = [] } = useQuery<ClubStaffRead[]>({
    queryKey: ["club-staff", clubId, currentSeason?.id],
    queryFn: () => staffApi.list(clubId, currentSeason?.id),
    enabled: segment === "squad" && !!currentSeason,
  });

  const { data: allPlayersForSquad = [] } = useQuery<PlayerRead[]>({
    queryKey: ["players"],
    queryFn: playersApi.list,
    enabled: segment === "squad",
  });
  const squadPlayerMap = new Map(allPlayersForSquad.map((p) => [p.id, p]));

  const submitMutation = useMutation({
    mutationFn: async () => {
      if (!currentProfile) {
        await profilesApi.create({ club_id: clubId, season_id: currentSeason!.id });
        const updated = await profilesApi.list();
        const newProfile = updated.find(
          (p) => p.club_id === clubId && p.season_id === currentSeason!.id
        );
        if (!newProfile) throw new Error("Could not create squad profile");
        return profilesApi.submit(newProfile.id);
      }
      return profilesApi.submit(currentProfile.id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profiles"] });
      toast.success("Squad list submitted to the league");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const { data: allRegistrations = [] } = useQuery<RegistrationRequestRead[]>({
    queryKey: ["registrations"],
    queryFn: registrationsApi.list,
    enabled: segment === "players",
  });

  const { data: allPlayers = [] } = useQuery<PlayerRead[]>({
    queryKey: ["players"],
    queryFn: playersApi.list,
    enabled: segment === "players",
  });

  // Club admins: users who have club_admin in their governance_roles for this club
  const clubAdmins = allUsers.filter(
    (u) =>
      !u.is_deleted &&
      (u.governance_roles ?? []).some(
        (gr) => gr.role === "club_admin" && gr.club_id === clubId
      )
  );

  const clubPlayerIds = new Set(
    allRegistrations
      .filter((r) => r.club_id === clubId && r.status === "accepted")
      .map((r) => r.player_id)
  );
  const clubPlayers = allPlayers.filter((p) => clubPlayerIds.has(p.id));

  const deleteStaffMutation = useMutation({
    mutationFn: (id: number) => staffApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["club-staff", clubId] });
      toast.success("Staff member removed");
      setDeleteStaffTarget(null);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const handleCoverChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setCoverUploading(true);
    try {
      const { url, fields, key } = await clubsApi.coverUploadUrl(
        clubId,
        file.name,
        file.type || "image/jpeg"
      );
      const formData = new FormData();
      Object.entries(fields).forEach(([k, v]) => formData.append(k, v));
      formData.append("file", file);
      const s3Res = await fetch(url, { method: "POST", body: formData });
      if (!s3Res.ok) throw new Error("Upload to S3 failed");
      await clubsApi.update(clubId, { cover_key: key });
      queryClient.invalidateQueries({ queryKey: ["club", clubId] });
      queryClient.invalidateQueries({ queryKey: ["clubs"] });
      toast.success("Cover photo updated");
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setCoverUploading(false);
      if (coverInputRef.current) coverInputRef.current.value = "";
    }
  };

  if (clubLoading) {
    return (
      <div className="p-6 space-y-4">
        <div className="h-8 bg-muted rounded animate-pulse w-48" />
        <div className="h-32 bg-muted rounded animate-pulse" />
      </div>
    );
  }

  if (!club) {
    return (
      <div className="p-6">
        <p className="text-muted-foreground">Club not found.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Back */}
      <button
        onClick={() => router.back()}
        className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Clubs
      </button>

      {/* Club header card with cover photo */}
      <div className="rounded-2xl border border-border bg-card overflow-hidden shadow-card">
        {/* Cover photo banner */}
        <div className="relative h-44 sm:h-52 bg-secondary">
          {club.cover_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={club.cover_url}
              alt={`${club.name} cover`}
              className="w-full h-full object-cover"
            />
          ) : (
            <div className="w-full h-full flex flex-col items-center justify-center gap-2 text-muted-foreground/40">
              <ImageIcon className="h-8 w-8" />
              <span className="text-xs font-medium">Club cover photo</span>
            </div>
          )}
          {/* Change cover button */}
          {canEdit && (
            <button
              type="button"
              onClick={() => coverInputRef.current?.click()}
              disabled={coverUploading}
              className="absolute top-3 right-3 flex items-center gap-1.5 px-3 py-1.5 rounded-[10px] bg-black/40 backdrop-blur text-white text-xs font-semibold hover:bg-black/60 disabled:opacity-50 transition-colors"
            >
              <Camera className="h-3.5 w-3.5" />
              {coverUploading ? "Uploading…" : "Change cover"}
            </button>
          )}
          <input
            ref={coverInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={handleCoverChange}
          />
        </div>

        {/* Logo + info row — logo overlaps cover bottom */}
        <div className="px-5 pb-5">
          <div className="flex items-end gap-4 -mt-8 sm:-mt-10 mb-4">
            {/* Logo overlapping cover */}
            <div className="relative shrink-0">
              <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-xl bg-primary/10 text-primary font-bold text-xl flex items-center justify-center overflow-hidden border-4 border-card shadow-card">
                {club.logo_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={club.logo_url}
                    alt={club.name}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <span className="text-lg">{club.code.slice(0, 3)}</span>
                )}
              </div>
            </div>
            <div className="flex-1 min-w-0 pb-1">
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="font-serif text-xl font-semibold">{club.name}</h1>
                <span className="font-mono text-xs px-2 py-0.5 rounded-md bg-secondary text-muted-foreground">
                  {club.code}
                </span>
                <StatusBadge status={club.status} />
              </div>
              {club.established_year && (
                <p className="eyebrow mt-0.5">Est. {club.established_year}</p>
              )}
            </div>
            {canEdit && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => setEditOpen(true)}
                className="shrink-0 mb-1"
              >
                <Pencil className="h-3.5 w-3.5" />
                Edit club
              </Button>
            )}
          </div>

          <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
            {club.email && (
              <span className="flex items-center gap-1.5">
                <Mail className="h-3.5 w-3.5" />
                {club.email}
              </span>
            )}
            {club.phone_number && (
              <span className="flex items-center gap-1.5">
                <Phone className="h-3.5 w-3.5" />
                {club.phone_number}
              </span>
            )}
            {club.short_name && (
              <span className="text-muted-foreground">{club.short_name}</span>
            )}
          </div>
        </div>
      </div>

      {/* Segment navigation */}
      <div className="flex border-b border-border overflow-x-auto">
        {SEGMENTS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setSegment(id)}
            className={`tab flex items-center gap-2 ${segment === id ? "tab-active" : ""}`}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* Segment content */}
      {segment === "overview" && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            {[
              { label: "Code", value: club.code, mono: true },
              { label: "Email", value: club.email ?? "—" },
              { label: "Phone", value: club.phone_number ?? "—" },
            ].map(({ label, value, mono }) => (
              <div key={label} className="rounded-lg border border-border bg-card p-4">
                <p className="text-xs text-muted-foreground mb-1">{label}</p>
                <p className={`text-sm font-medium ${mono ? "font-mono" : ""}`}>{value}</p>
              </div>
            ))}
          </div>

          {/* Officials section — only show if any of them are set */}
          {(club.president_name || club.secretary_name || club.treasurer_name) && (
            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                Club Officials
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {[
                  { label: "President", value: club.president_name },
                  { label: "Secretary", value: club.secretary_name },
                  { label: "Treasurer", value: club.treasurer_name },
                ]
                  .filter((o) => o.value)
                  .map(({ label, value }) => (
                    <div key={label} className="rounded-lg border border-border bg-card p-4">
                      <p className="text-xs text-muted-foreground mb-1">{label}</p>
                      <p className="text-sm font-medium">{value}</p>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>
      )}

      {segment === "players" && (
        <div>
          <p className="text-xs text-muted-foreground mb-3">
            {clubPlayers.length} registered player{clubPlayers.length !== 1 ? "s" : ""}
          </p>
          {clubPlayers.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border p-8 text-center">
              <Shirt className="h-6 w-6 text-muted-foreground mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">No players registered to this club</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {clubPlayers.map((player) => (
                <button
                  key={player.id}
                  onClick={() => router.push(`/dashboard/players/${player.id}`)}
                  className="flex items-center gap-3 p-3 rounded-lg border border-border bg-card hover:bg-muted/50 transition-colors text-left"
                >
                  <div className="flex items-center justify-center w-9 h-9 rounded-full bg-primary/10 text-primary text-xs font-bold shrink-0">
                    {player.photo_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={player.photo_url}
                        alt={player.full_name}
                        className="w-full h-full rounded-full object-cover"
                      />
                    ) : (
                      player.full_name.split(" ").map((n) => n[0]).join("").slice(0, 2)
                    )}
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate">{player.full_name}</p>
                    <p className="text-xs text-muted-foreground font-mono">
                      {player.league_player_code}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {segment === "staff" && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs text-muted-foreground">
              {staff.length} staff member{staff.length !== 1 ? "s" : ""}
            </p>
            {isOwnClubAdmin && (
              <Button size="sm" onClick={() => setAddStaffOpen(true)} className="gap-1.5">
                <Plus className="h-4 w-4" />
                Add staff
              </Button>
            )}
          </div>
          {staff.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border p-8 text-center">
              <UserSquare2 className="h-6 w-6 text-muted-foreground mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">No support staff added yet</p>
              {isOwnClubAdmin && (
                <Button
                  size="sm"
                  variant="outline"
                  className="mt-3"
                  onClick={() => setAddStaffOpen(true)}
                >
                  Add staff
                </Button>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {staff.map((s) => (
                <div
                  key={s.id}
                  className="flex items-center gap-3 p-3 rounded-lg border border-border bg-card"
                >
                  <div className="flex items-center justify-center w-9 h-9 rounded-full bg-muted text-muted-foreground text-xs font-bold shrink-0">
                    {s.full_name.split(" ").map((n) => n[0]).join("").slice(0, 2)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{s.full_name}</p>
                    <p className="text-xs text-muted-foreground">{s.role}</p>
                  </div>
                  {isOwnClubAdmin && (
                    <button
                      onClick={() => setDeleteStaffTarget(s)}
                      className="text-muted-foreground hover:text-destructive transition-colors shrink-0"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {segment === "admins" && (
        <div>
          <p className="text-xs text-muted-foreground mb-3">
            {clubAdmins.length} admin{clubAdmins.length !== 1 ? "s" : ""}
          </p>
          {clubAdmins.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border p-8 text-center">
              <Users className="h-6 w-6 text-muted-foreground mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">No club admins assigned</p>
              <p className="text-xs text-muted-foreground mt-1">
                Assign the club_admin role to a user from the Users page.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {clubAdmins.map((admin) => (
                <button
                  key={admin.id}
                  onClick={() => router.push(`/dashboard/users/${admin.id}`)}
                  className="flex items-center gap-3 p-3 rounded-lg border border-border bg-card hover:bg-muted/50 transition-colors text-left"
                >
                  <div className="flex items-center justify-center w-9 h-9 rounded-full bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 text-xs font-bold shrink-0">
                    {admin.email[0].toUpperCase()}
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate">{admin.email}</p>
                    <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                      {admin.member_type && (
                        <StatusBadge status={admin.member_type} />
                      )}
                      <StatusBadge status="club_admin" />
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {segment === "squad" && (
        <div className="space-y-6">
          {!currentSeason ? (
            <p className="text-sm text-muted-foreground">No season available.</p>
          ) : (
            <>
              {/* Status banner */}
              <div className="flex items-center justify-between p-4 rounded-lg border border-border bg-card">
                <div>
                  <p className="text-sm font-semibold">{currentSeason.name}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Registration:{" "}
                    {formatDate(currentSeason.registration_open_at)} —{" "}
                    {formatDate(currentSeason.registration_close_at)}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  {currentProfile && (
                    <StatusBadge status={currentProfile.status} />
                  )}
                  {isOwnClubAdmin &&
                    (!currentProfile ||
                      currentProfile.status === "draft" ||
                      currentProfile.status === "returned") && (
                      <Button
                        size="sm"
                        onClick={() => submitMutation.mutate()}
                        disabled={submitMutation.isPending || squadRegistrations.length === 0}
                        className="gap-1.5"
                      >
                        <CheckCircle2 className="h-4 w-4" />
                        {submitMutation.isPending ? "Submitting…" : "Submit squad list"}
                      </Button>
                    )}
                  {currentProfile?.status === "submitted" ||
                  currentProfile?.status === "resubmitted" ? (
                    <p className="text-xs text-muted-foreground">
                      Submitted {formatDate(currentProfile.submitted_at)}
                    </p>
                  ) : null}
                </div>
              </div>

              {/* Players */}
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                  Players ({squadRegistrations.length}/30)
                </p>
                {squadRegistrations.length === 0 ? (
                  <div className="rounded-lg border border-dashed border-border p-6 text-center">
                    <Shirt className="h-5 w-5 text-muted-foreground mx-auto mb-2" />
                    <p className="text-sm text-muted-foreground">
                      No players registered yet. Send registration requests from the
                      Registrations page.
                    </p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {squadRegistrations.map((reg) => {
                      const player = squadPlayerMap.get(reg.player_id);
                      return (
                        <button
                          key={reg.id}
                          onClick={() =>
                            router.push(`/dashboard/players/${reg.player_id}`)
                          }
                          className="flex items-center gap-3 p-3 rounded-lg border border-border bg-card hover:bg-muted/50 transition-colors text-left"
                        >
                          <div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary/10 text-primary text-xs font-bold shrink-0">
                            {player
                              ? player.full_name
                                  .split(" ")
                                  .map((n) => n[0])
                                  .join("")
                                  .slice(0, 2)
                              : "?"}
                          </div>
                          <div className="min-w-0">
                            <p className="text-sm font-medium truncate">
                              {player?.full_name ?? `Player ${reg.player_id}`}
                            </p>
                            <p className="text-xs text-muted-foreground font-mono">
                              {player?.league_player_code ?? ""}
                            </p>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Staff */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Support Staff ({squadStaff.length}/6)
                  </p>
                  {isOwnClubAdmin && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setAddStaffOpen(true)}
                      className="gap-1.5 h-7 text-xs"
                    >
                      <Plus className="h-3 w-3" />
                      Add
                    </Button>
                  )}
                </div>
                {squadStaff.length === 0 ? (
                  <div className="rounded-lg border border-dashed border-border p-6 text-center">
                    <UserSquare2 className="h-5 w-5 text-muted-foreground mx-auto mb-2" />
                    <p className="text-sm text-muted-foreground">No support staff added yet.</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {squadStaff.map((s) => (
                      <div
                        key={s.id}
                        className="flex items-center gap-3 p-3 rounded-lg border border-border bg-card"
                      >
                        <div className="flex items-center justify-center w-8 h-8 rounded-full bg-muted text-muted-foreground text-xs font-bold shrink-0">
                          {s.full_name.split(" ").map((n) => n[0]).join("").slice(0, 2)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">{s.full_name}</p>
                          <p className="text-xs text-muted-foreground">{s.role}</p>
                        </div>
                        {isOwnClubAdmin && (
                          <button
                            onClick={() => setDeleteStaffTarget(s)}
                            className="text-muted-foreground hover:text-destructive transition-colors"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {/* Dialogs */}
      {club && (
        <EditClubDialog
          club={club}
          open={editOpen}
          onOpenChange={setEditOpen}
        />
      )}

      <AddStaffDialog
        clubId={clubId}
        open={addStaffOpen}
        onOpenChange={setAddStaffOpen}
      />

      {deleteStaffTarget && (
        <ConfirmDialog
          open
          onOpenChange={(v) => { if (!v) setDeleteStaffTarget(null); }}
          title="Remove staff member?"
          description={`Remove ${deleteStaffTarget.full_name} (${deleteStaffTarget.role})?`}
          confirmLabel="Remove"
          destructive
          loading={deleteStaffMutation.isPending}
          onConfirm={() => deleteStaffMutation.mutate(deleteStaffTarget.id)}
        />
      )}
    </div>
  );
}
