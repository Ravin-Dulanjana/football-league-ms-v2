"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm, Controller } from "react-hook-form";
import { useRouter } from "next/navigation";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { ChevronRight, Filter, MoreHorizontal, Plus, RefreshCw, Search, Trash2, Users, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
import { usersApi, clubsApi } from "@/lib/api";
import { cn, formatDate, formatRelative } from "@/lib/utils";
import type { AccountAction, AssignRoleRequest, ClubRead, RevokeRoleRequest, UserRead } from "@/types";

// ---------------------------------------------------------------------------
// Create user dialog
// ---------------------------------------------------------------------------

const createSchema = z.object({
  email: z.string().email("Invalid email"),
  temporary_password: z.string().min(8, "At least 8 characters"),
  full_name: z.string().min(1, "Required"),
  date_of_birth: z.string().min(1, "Required"),
  nic_number: z.string().min(1, "Required"),
  phone_number: z.string().min(1, "Phone number is required"),
});

type CreateForm = z.infer<typeof createSchema>;

function CreateUserDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const queryClient = useQueryClient();

  const form = useForm<CreateForm>({
    resolver: zodResolver(createSchema),
    defaultValues: {
      email: "",
      temporary_password: "",
      full_name: "",
      date_of_birth: "",
      nic_number: "",
      phone_number: "",
    },
  });

  const mutation = useMutation({
    mutationFn: (data: CreateForm) =>
      usersApi.create({
        email: data.email,
        role: "player",
        member_type: "player",
        temporary_password: data.temporary_password,
        full_name: data.full_name,
        date_of_birth: data.date_of_birth,
        nic_number: data.nic_number,
        phone_number: data.phone_number,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      toast.success("Member added — they will be prompted to set a password on first login");
      onOpenChange(false);
      form.reset();
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add member</DialogTitle>
        </DialogHeader>
        <form onSubmit={form.handleSubmit((d) => mutation.mutate(d))} className="space-y-4">

          <div className="space-y-1.5">
            <Label htmlFor="u-email">Email *</Label>
            <Input id="u-email" type="email" {...form.register("email")} />
            {form.formState.errors.email && (
              <p className="text-xs text-destructive">{form.formState.errors.email.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="full_name">Full name *</Label>
            <Input id="full_name" {...form.register("full_name")} placeholder="e.g. Kamal Perera" />
            {form.formState.errors.full_name && (
              <p className="text-xs text-destructive">{form.formState.errors.full_name.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="date_of_birth">Date of birth *</Label>
            <Input id="date_of_birth" type="date" {...form.register("date_of_birth")} />
            {form.formState.errors.date_of_birth && (
              <p className="text-xs text-destructive">{form.formState.errors.date_of_birth.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="nic_number">NIC number *</Label>
            <Input id="nic_number" {...form.register("nic_number")} placeholder="e.g. 901234567V" />
            <p className="text-xs text-muted-foreground">Required for official league registration</p>
            {form.formState.errors.nic_number && (
              <p className="text-xs text-destructive">{form.formState.errors.nic_number.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="phone_number">Phone number *</Label>
            <Input id="phone_number" type="tel" {...form.register("phone_number")} placeholder="e.g. 0771234567" />
            {form.formState.errors.phone_number && (
              <p className="text-xs text-destructive">{form.formState.errors.phone_number.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="tmp-pw">Temporary password *</Label>
            <Input id="tmp-pw" type="password" {...form.register("temporary_password")} placeholder="Min. 8 characters" />
            <p className="text-xs text-muted-foreground">They will be asked to change this when they first log in</p>
            {form.formState.errors.temporary_password && (
              <p className="text-xs text-destructive">{form.formState.errors.temporary_password.message}</p>
            )}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Adding…" : "Add member"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Assign role dialog
// ---------------------------------------------------------------------------

const assignRoleSchema = z
  .object({
    new_role: z.enum(["league_admin", "club_admin"] as const),
    club_id: z.number().optional(),
    reason: z.string().min(1, "Reason is required"),
  })
  .superRefine((val, ctx) => {
    if (val.new_role === "club_admin" && !val.club_id) {
      ctx.addIssue({ code: "custom", path: ["club_id"], message: "Club is required for club_admin role" });
    }
  });

type AssignRoleForm = z.infer<typeof assignRoleSchema>;

function AssignRoleDialog({
  user,
  open,
  onOpenChange,
  callerRole,
  callerClubId,
}: {
  user: UserRead | null;
  open: boolean;
  onOpenChange: (v: boolean) => void;
  callerRole: string | undefined;
  callerClubId: number | null | undefined;
}) {
  const queryClient = useQueryClient();

  // club_admin callers can only assign club_admin; pre-set their club
  const isCallerClubAdmin = callerRole === "club_admin";

  const { data: clubs } = useQuery<ClubRead[]>({
    queryKey: ["clubs"],
    queryFn: clubsApi.list,
    enabled: open && !isCallerClubAdmin,
  });

  // roles the caller is permitted to assign
  const assignableRoles = isCallerClubAdmin
    ? (["club_admin"] as const)
    : (["league_admin", "club_admin"] as const);

  const form = useForm<AssignRoleForm>({
    resolver: zodResolver(assignRoleSchema),
    defaultValues: {
      new_role: isCallerClubAdmin ? "club_admin" : "league_admin",
      club_id: isCallerClubAdmin && callerClubId ? callerClubId : undefined,
      reason: "",
    },
  });

  const newRole = form.watch("new_role");

  const mutation = useMutation({
    mutationFn: (data: AssignRoleForm) => {
      const payload: AssignRoleRequest = {
        new_role: data.new_role,
        club_id: isCallerClubAdmin ? callerClubId ?? undefined : data.club_id ?? null,
        reason: data.reason,
      };
      return usersApi.assignRole(user!.id, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      toast.success("Role added successfully");
      toast.info("The user must log out and back in for role changes to take effect.", { duration: 7000 });
      onOpenChange(false);
      form.reset();
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Assign Role</DialogTitle>
          {user && <p className="text-sm text-muted-foreground pt-1">{user.email}</p>}
        </DialogHeader>

        {user && (
          <div className="-mt-2 pb-1 space-y-1">
            {(user.governance_roles ?? []).length > 0 && (
              <p className="text-xs text-muted-foreground">
                Current governance roles:{" "}
                <span className="font-medium">
                  {(user.governance_roles ?? []).map((g) => g.role.replace(/_/g, " ")).join(", ")}
                </span>
              </p>
            )}
            <p className="text-xs text-amber-600 dark:text-amber-400">
              Governance roles are <strong>additive</strong> — assigning league admin keeps existing club admin.
            </p>
          </div>
        )}

        <form onSubmit={form.handleSubmit((d) => mutation.mutate(d))} className="space-y-4">
          <div className="space-y-1.5">
            <Label>New Role *</Label>
            <Controller
              control={form.control}
              name="new_role"
              render={({ field }) => (
                <Select onValueChange={field.onChange} value={field.value} disabled={isCallerClubAdmin}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {assignableRoles.map((r) => (
                      <SelectItem key={r} value={r}>
                        {r.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </div>

          {newRole === "club_admin" && !isCallerClubAdmin && (
            <div className="space-y-1.5">
              <Label>Club *</Label>
              <Controller
                control={form.control}
                name="club_id"
                render={({ field }) => (
                  <Select onValueChange={(v) => field.onChange(Number(v))} value={field.value ? String(field.value) : ""}>
                    <SelectTrigger><SelectValue placeholder="Select club" /></SelectTrigger>
                    <SelectContent>
                      {clubs?.map((c) => (
                        <SelectItem key={c.id} value={String(c.id)}>{c.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
              {form.formState.errors.club_id && (
                <p className="text-xs text-destructive">{form.formState.errors.club_id.message}</p>
              )}
            </div>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="ar-reason">Reason *</Label>
            <Input id="ar-reason" {...form.register("reason")} placeholder="e.g. Elected club president at AGM 2026" />
            {form.formState.errors.reason && (
              <p className="text-xs text-destructive">{form.formState.errors.reason.message}</p>
            )}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Assigning…" : "Assign role"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Revoke role dialog
// ---------------------------------------------------------------------------

function RevokeRoleDialog({
  user,
  revokeTarget,
  open,
  onOpenChange,
}: {
  user: UserRead | null;
  revokeTarget: { role: string; club_id: number | null } | null;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");

  const mutation = useMutation({
    mutationFn: () => {
      const payload: RevokeRoleRequest = {
        role: revokeTarget!.role,
        club_id: revokeTarget!.club_id ?? undefined,
        reason,
      };
      return usersApi.revokeRole(user!.id, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      toast.success(`${revokeTarget?.role?.replace(/_/g, " ")} role revoked`);
      toast.info("The user must log out and back in for role changes to take effect.", { duration: 7000 });
      onOpenChange(false);
      setReason("");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) setReason(""); onOpenChange(v); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Revoke Role</DialogTitle>
          {user && revokeTarget && (
            <p className="text-sm text-muted-foreground pt-1">
              Remove <strong>{revokeTarget.role.replace(/_/g, " ")}</strong> from {user.email}
            </p>
          )}
        </DialogHeader>
        <div className="space-y-1.5">
          <Label htmlFor="rr-reason">Reason *</Label>
          <Input
            id="rr-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. Stepped down at AGM 2026"
          />
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button
            variant="destructive"
            disabled={!reason.trim() || mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {mutation.isPending ? "Revoking…" : "Revoke role"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Role cell
// ---------------------------------------------------------------------------

function RoleCell({ user }: { user: UserRead }) {
  const govRoles = user.governance_roles ?? [];
  return (
    <div className="flex items-center gap-1 flex-wrap">
      {govRoles.map((gr, i) => (
        <StatusBadge key={`${gr.role}-${i}`} status={gr.role} />
      ))}
      {govRoles.length === 0 && <StatusBadge status="member" />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

type Tab = "active" | "deleted";

export default function UsersPage() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("active");
  const [createOpen, setCreateOpen] = useState(false);
  const [assignRoleTarget, setAssignRoleTarget] = useState<UserRead | null>(null);
  const [revokeRoleTarget, setRevokeRoleTarget] = useState<{
    user: UserRead;
    role: string;
    club_id: number | null;
  } | null>(null);
  const [hardDeleteTarget, setHardDeleteTarget] = useState<UserRead | null>(null);
  const [restoreTarget, setRestoreTarget] = useState<UserRead | null>(null);
  const [actionTarget, setActionTarget] = useState<{
    user: UserRead;
    action: AccountAction;
    label: string;
  } | null>(null);
  const [clubFilter, setClubFilter] = useState<number | "all">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const queryClient = useQueryClient();
  const { isSuperAdmin, isLeagueLevel, isClubAdmin, isAnyAdmin, user: currentUser } = useCurrentUser();

  const { data: clubs } = useQuery<ClubRead[]>({
    queryKey: ["clubs"],
    queryFn: clubsApi.list,
  });

  const clubMap = Object.fromEntries((clubs ?? []).map((c) => [c.id, c.name]));

  const { data: activeUsers, isLoading: activeLoading, error: activeError, refetch: refetchActive } = useQuery<UserRead[]>({
    queryKey: ["users"],
    queryFn: () => usersApi.list(false),
  });

  const { data: deletedUsers, isLoading: deletedLoading, error: deletedError, refetch: refetchDeleted } = useQuery<UserRead[]>({
    queryKey: ["users", "deleted"],
    queryFn: () => usersApi.list(true).then((all) => all.filter((u) => u.is_deleted)),
    enabled: isSuperAdmin && tab === "deleted",
  });

  const actionMutation = useMutation({
    mutationFn: ({ userId, action, reason }: { userId: number; action: AccountAction; reason: string }) =>
      usersApi.accountAction(userId, { action, reason }),
    onSuccess: (_, { action }) => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      const labels: Record<AccountAction, string> = {
        activate: "activated", deactivate: "deactivated", soft_delete: "deleted",
        reset_password: "password reset — a temporary password has been sent", update_mobile: "mobile updated",
      };
      toast.success(`User ${labels[action]}`);
      setActionTarget(null);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const hardDeleteMutation = useMutation({
    mutationFn: (userId: number) => usersApi.hardDelete(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      queryClient.invalidateQueries({ queryKey: ["users", "deleted"] });
      toast.success("User permanently deleted");
      setHardDeleteTarget(null);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const restoreMutation = useMutation({
    mutationFn: (userId: number) => usersApi.restore(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      queryClient.invalidateQueries({ queryKey: ["users", "deleted"] });
      toast.success("User restored — reset their password so they can log in again");
      setRestoreTarget(null);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const isLoading = tab === "active" ? activeLoading : deletedLoading;
  const error = tab === "active" ? activeError : deletedError;
  const refetch = tab === "active" ? refetchActive : refetchDeleted;
  const rawUsers = tab === "active" ? activeUsers : deletedUsers;

  // Client-side filters
  const q = searchQuery.trim().toLowerCase();
  const users = rawUsers?.filter((u) => {
    if (clubFilter !== "all" && u.club_id !== clubFilter) return false;
    if (q) {
      const matchEmail = u.email.toLowerCase().includes(q);
      const matchName = u.full_name?.toLowerCase().includes(q) ?? false;
      if (!matchEmail && !matchName) return false;
    }
    return true;
  });

  // Which roles can the current user manage?
  const canManageRoles = isAnyAdmin;

  return (
    <div>
      <PageHeader
        title="Members"
        description="All members in the league"
        action={
          (isLeagueLevel || isClubAdmin) && tab === "active" ? (
            <Button size="sm" onClick={() => setCreateOpen(true)} className="gap-1.5">
              <Plus className="h-4 w-4" />
              Add member
            </Button>
          ) : undefined
        }
      />

      {/* Tabs */}
      {isSuperAdmin && (
        <div className="flex gap-1 mb-4 border-b border-border">
          {(["active", "deleted"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={cn(
                "px-4 py-2 text-sm font-medium -mb-px border-b-2 transition-colors",
                tab === t
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              )}
            >
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
      )}

      {/* Filters */}
      {tab === "active" && (
        <div className="flex flex-wrap items-center gap-2 mb-4">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by name or email…"
              className="pl-8 h-8 w-56 text-sm"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                <X className="h-3 w-3" />
              </button>
            )}
          </div>
          {clubs && clubs.length > 0 && (
            <>
              <Filter className="h-4 w-4 text-muted-foreground shrink-0" />
              <Select
                value={clubFilter === "all" ? "all" : String(clubFilter)}
                onValueChange={(v) => setClubFilter(v === "all" ? "all" : Number(v))}
              >
                <SelectTrigger className="w-52 h-8 text-sm">
                  <SelectValue placeholder="All clubs" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All clubs</SelectItem>
                  {clubs.map((c) => (
                    <SelectItem key={c.id} value={String(c.id)}>{c.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {clubFilter !== "all" && (
                <button
                  onClick={() => setClubFilter("all")}
                  className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                >
                  <X className="h-3 w-3" /> Clear
                </button>
              )}
            </>
          )}
        </div>
      )}

      {isLoading ? (
        <DataTableSkeleton columns={7} />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : !users?.length ? (
        <EmptyState
          title={tab === "deleted" ? "No deleted members" : "No members yet"}
          icon={<Users className="h-6 w-6" />}
          action={
            (isLeagueLevel || isClubAdmin) && tab === "active"
              ? { label: "Add member", onClick: () => setCreateOpen(true) }
              : undefined
          }
        />
      ) : tab === "active" ? (
        <div className="rounded-lg border border-border overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Email</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Club</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Last login</TableHead>
                <TableHead>Created</TableHead>
                <TableHead />
                <TableHead className="w-6" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((user) => {
                const govRoles = user.governance_roles ?? [];
                return (
                  <TableRow
                    key={user.id}
                    className="hover:bg-muted/50 cursor-pointer"
                    onClick={() => router.push(`/dashboard/users/${user.id}`)}
                  >
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm">{user.email}</span>
                        {user.force_password_change && (
                          <span className="text-[10px] bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded-sm dark:bg-amber-900/30 dark:text-amber-400">
                            pw change
                          </span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {user.full_name ?? "—"}
                    </TableCell>
                    <TableCell><RoleCell user={user} /></TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {user.club_id ? (clubMap[user.club_id] ?? `Club ${user.club_id}`) : "—"}
                    </TableCell>
                    <TableCell><StatusBadge status={user.is_active ? "active" : "inactive"} /></TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {user.last_login_at ? formatRelative(user.last_login_at) : "Never"}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">{formatDate(user.created_at)}</TableCell>
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      {(isLeagueLevel || canManageRoles) && (
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-7 w-7">
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            {/* Deactivate / reset — league admin and super admin only */}
                            {isLeagueLevel && (
                              <>
                                {user.is_active ? (
                                  <DropdownMenuItem onClick={() => setActionTarget({ user, action: "deactivate", label: "Deactivate user" })}>
                                    Deactivate
                                  </DropdownMenuItem>
                                ) : (
                                  <DropdownMenuItem onClick={() => setActionTarget({ user, action: "activate", label: "Activate user" })}>
                                    Activate
                                  </DropdownMenuItem>
                                )}
                                <DropdownMenuItem onClick={() => setActionTarget({ user, action: "reset_password", label: "Reset password" })}>
                                  Reset password
                                </DropdownMenuItem>
                              </>
                            )}

                            {/* Role management — all admins */}
                            {canManageRoles && (
                              <>
                                {isLeagueLevel && <DropdownMenuSeparator />}
                                <DropdownMenuItem onClick={() => setAssignRoleTarget(user)}>
                                  Assign role
                                </DropdownMenuItem>
                                {govRoles.map((gr) => (
                                  <DropdownMenuItem
                                    key={`revoke-${gr.role}`}
                                    className="text-destructive focus:text-destructive"
                                    onClick={() => setRevokeRoleTarget({ user, role: gr.role, club_id: gr.club_id ?? null })}
                                  >
                                    Revoke {gr.role.replace(/_/g, " ")}
                                  </DropdownMenuItem>
                                ))}
                              </>
                            )}

                            {isSuperAdmin && (
                              <>
                                <DropdownMenuSeparator />
                                <DropdownMenuItem
                                  className="text-destructive focus:text-destructive"
                                  onClick={() => setActionTarget({ user, action: "soft_delete", label: "Delete user" })}
                                >
                                  Delete user
                                </DropdownMenuItem>
                              </>
                            )}
                          </DropdownMenuContent>
                        </DropdownMenu>
                      )}
                    </TableCell>
                    <TableCell className="w-6">
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      ) : (
        /* Deleted users table */
        <div className="rounded-lg border border-border overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Email</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Club</TableHead>
                <TableHead>Deleted</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((user) => (
                <TableRow key={user.id} className="opacity-70">
                  <TableCell>
                    <span className="font-medium text-sm line-through text-muted-foreground">{user.email}</span>
                  </TableCell>
                  <TableCell><RoleCell user={user} /></TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {user.club_id ? (clubMap[user.club_id] ?? `Club ${user.club_id}`) : "—"}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">{formatDate(user.created_at)}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Button size="sm" variant="outline" className="h-7 gap-1.5 text-xs" onClick={() => setRestoreTarget(user)}>
                        <RefreshCw className="h-3 w-3" /> Restore
                      </Button>
                      <Button
                        size="sm" variant="ghost"
                        className="h-7 gap-1.5 text-xs text-destructive hover:text-destructive"
                        onClick={() => setHardDeleteTarget(user)}
                      >
                        <Trash2 className="h-3 w-3" /> Delete forever
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Dialogs */}
      <CreateUserDialog open={createOpen} onOpenChange={setCreateOpen} />

      <AssignRoleDialog
        user={assignRoleTarget}
        open={!!assignRoleTarget}
        onOpenChange={(v) => { if (!v) setAssignRoleTarget(null); }}
        callerRole={currentUser?.role}
        callerClubId={currentUser?.club_id}
      />

      <RevokeRoleDialog
        user={revokeRoleTarget?.user ?? null}
        revokeTarget={revokeRoleTarget ? { role: revokeRoleTarget.role, club_id: revokeRoleTarget.club_id } : null}
        open={!!revokeRoleTarget}
        onOpenChange={(v) => { if (!v) setRevokeRoleTarget(null); }}
      />

      {actionTarget && (
        <ConfirmDialog
          open
          onOpenChange={(v) => { if (!v) setActionTarget(null); }}
          title={actionTarget.label}
          description={`You are about to ${actionTarget.action.replace(/_/g, " ")} ${actionTarget.user.email}.`}
          confirmLabel={actionTarget.label}
          requireReason
          destructive={actionTarget.action === "soft_delete"}
          loading={actionMutation.isPending}
          onConfirm={(reason) => actionMutation.mutate({ userId: actionTarget.user.id, action: actionTarget.action, reason: reason ?? "" })}
        />
      )}

      {restoreTarget && (
        <ConfirmDialog
          open
          onOpenChange={(v) => { if (!v) setRestoreTarget(null); }}
          title="Restore user"
          description={`Restore ${restoreTarget.email}? The account will be re-activated.`}
          confirmLabel="Restore"
          loading={restoreMutation.isPending}
          onConfirm={() => restoreMutation.mutate(restoreTarget.id)}
        />
      )}

      {hardDeleteTarget && (
        <ConfirmDialog
          open
          onOpenChange={(v) => { if (!v) setHardDeleteTarget(null); }}
          title="Permanently delete user"
          description={`This will permanently delete ${hardDeleteTarget.email}. This cannot be undone.`}
          confirmLabel="Delete forever"
          destructive
          loading={hardDeleteMutation.isPending}
          onConfirm={() => hardDeleteMutation.mutate(hardDeleteTarget.id)}
        />
      )}
    </div>
  );
}
