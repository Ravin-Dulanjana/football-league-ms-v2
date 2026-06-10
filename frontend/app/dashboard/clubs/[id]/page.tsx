"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import {
  ArrowLeft,
  Building2,
  Mail,
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
import { clubsApi, staffApi, usersApi, registrationsApi, playersApi, seasonsApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type {
  ClubRead,
  ClubStaffRead,
  PlayerRead,
  RegistrationRequestRead,
  SeasonRead,
  UserRead,
} from "@/types";

// ---------------------------------------------------------------------------
// Segment navigation
// ---------------------------------------------------------------------------

type Segment = "overview" | "players" | "staff" | "admins";

const SEGMENTS: { id: Segment; label: string; icon: React.ElementType }[] = [
  { id: "overview", label: "Overview", icon: Building2 },
  { id: "players", label: "Players", icon: Shirt },
  { id: "staff", label: "Support Staff", icon: UserSquare2 },
  { id: "admins", label: "Admins", icon: Shield },
];

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
  const [deleteStaffTarget, setDeleteStaffTarget] = useState<ClubStaffRead | null>(null);
  const queryClient = useQueryClient();
  const { user, isClubAdmin } = useCurrentUser();

  // Is this the club admin of THIS specific club?
  const isOwnClubAdmin = isClubAdmin && user?.club_id === clubId;

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

  const clubAdmins = allUsers.filter(
    (u) => u.club_id === clubId && u.role === "club_admin" && !u.is_deleted
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

      {/* Club header card */}
      <div className="rounded-xl border border-border bg-card p-6">
        <div className="flex items-start gap-5">
          {/* Logo / initials */}
          <div className="flex items-center justify-center w-16 h-16 rounded-xl bg-primary/10 text-primary font-bold text-xl shrink-0">
            {club.logo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={club.logo_url}
                alt={club.name}
                className="w-full h-full rounded-xl object-cover"
              />
            ) : (
              club.code.slice(0, 3)
            )}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-xl font-semibold">{club.name}</h1>
              <span className="font-mono text-xs px-2 py-0.5 rounded-md bg-muted text-muted-foreground">
                {club.code}
              </span>
              <StatusBadge status={club.status} />
            </div>
            {club.short_name && (
              <p className="text-sm text-muted-foreground mt-0.5">{club.short_name}</p>
            )}
            {club.email && (
              <p className="flex items-center gap-1.5 text-sm text-muted-foreground mt-1.5">
                <Mail className="h-3.5 w-3.5" />
                {club.email}
              </p>
            )}
          </div>

          <p className="text-xs text-muted-foreground shrink-0">
            Since {formatDate(club.created_at)}
          </p>
        </div>
      </div>

      {/* Segment navigation */}
      <div className="flex gap-1 p-1 bg-muted rounded-lg w-fit">
        {SEGMENTS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setSegment(id)}
            className={`flex items-center gap-2 px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
              segment === id
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* Segment content */}
      {segment === "overview" && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { label: "Code", value: club.code, mono: true },
            { label: "Status", value: <StatusBadge status={club.status} /> },
            { label: "Contact", value: club.email ?? "—" },
            { label: "Created", value: formatDate(club.created_at) },
          ].map(({ label, value, mono }) => (
            <div key={label} className="rounded-lg border border-border bg-card p-4">
              <p className="text-xs text-muted-foreground mb-1">{label}</p>
              <p className={`text-sm font-medium ${mono ? "font-mono" : ""}`}>{value}</p>
            </div>
          ))}
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
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <StatusBadge status={admin.is_active ? "active" : "inactive"} />
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Dialogs */}
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
