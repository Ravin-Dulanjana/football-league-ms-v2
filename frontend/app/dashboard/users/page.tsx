"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm, Controller } from "react-hook-form";
import { useRouter } from "next/navigation";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { ChevronRight, MoreHorizontal, Plus, RefreshCw, Trash2, Users } from "lucide-react";

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
import type { AccountAction, AssignRoleRequest, ClubRead, MemberType, UserRead, UserRole } from "@/types";

// ---------------------------------------------------------------------------
// Create user dialog
// ---------------------------------------------------------------------------

// accountType drives the form UI. It maps to a backend role as follows:
//   player     → role=player     (player profile required)
//   club_staff → role=club_staff (club required; auto-set for club_admin)
//   account    → role=club_staff, no club (generic user — assign a role later)
//
// club_admin and super_admin are never created via this form.
// Governance roles (league_admin, club_admin) are assigned after creation
// using the Assign Role action.

type AccountType = "player" | "club_staff" | "account";

function makeCreateSchema(creatorIsClubAdmin: boolean) {
  return z
    .object({
      email: z.string().email("Invalid email"),
      account_type: z.enum(["player", "club_staff", "account"] as const),
      club_id: z.number().optional(),
      temporary_password: z.string().min(8, "At least 8 characters"),
      full_name: z.string().min(1, "Required"),
      date_of_birth: z.string().min(1, "Required"),
      nic_number: z.string().min(1, "Required"),
    })
    .superRefine((val, ctx) => {
      // League/super admin creating club_staff must pick a club.
      // Club admins skip the picker — their club is auto-assigned server-side.
      if (val.account_type === "club_staff" && !creatorIsClubAdmin && !val.club_id) {
        ctx.addIssue({ code: "custom", path: ["club_id"], message: "Select a club" });
      }
    });
}

function CreateUserDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const { isClubAdmin: creatorIsClubAdmin } = useCurrentUser();

  // Only load clubs when the creator can pick one (league/super admin)
  const { data: clubs } = useQuery<ClubRead[]>({
    queryKey: ["clubs"],
    queryFn: clubsApi.list,
    enabled: open && !creatorIsClubAdmin,
  });

  const schema = makeCreateSchema(creatorIsClubAdmin);
  type CreateForm = z.infer<typeof schema>;

  const form = useForm<CreateForm>({
    resolver: zodResolver(schema),
    defaultValues: {
      email: "",
      account_type: "player",
      temporary_password: "",
      full_name: "",
      date_of_birth: "",
      nic_number: "",
    },
  });

  const accountType = form.watch("account_type") as AccountType;

  const ACCOUNT_TYPE_LABELS: Record<AccountType, { label: string; hint: string }> = {
    player: {
      label: "Player",
      hint: "Creates a player profile. Club assigned through registration.",
    },
    club_staff: {
      label: "Club Staff",
      hint: creatorIsClubAdmin
        ? "Staff member for your club (coach, physio, secretary, etc.)."
        : "Staff member for a specific club.",
    },
    account: {
      label: "Account",
      hint: "Generic user with no club yet. Assign a role after creation.",
    },
  };

  // Which types are available to this creator?
  const availableTypes: AccountType[] = creatorIsClubAdmin
    ? ["player", "club_staff"]
    : ["player", "club_staff", "account"];

  const mutation = useMutation({
    mutationFn: (data: CreateForm) => {
      // account_type → backend role + member_type
      const roleMap: Record<AccountType, UserRole> = {
        player: "player",
        club_staff: "club_staff",
        account: "club_staff", // generic user: club_staff role, no club, member_type=user
      };
      const memberTypeMap: Record<AccountType, MemberType> = {
        player: "player",
        club_staff: "club_staff",
        account: "user",
      };
      return usersApi.create({
        email: data.email,
        role: roleMap[data.account_type as AccountType],
        member_type: memberTypeMap[data.account_type as AccountType],
        // club_id: for club_admin creators, omit it — the service auto-injects.
        //          for league/super admin creating club_staff, pass the picker value.
        club_id: !creatorIsClubAdmin && data.account_type === "club_staff"
          ? data.club_id
          : undefined,
        temporary_password: data.temporary_password,
        full_name: data.full_name,
        date_of_birth: data.date_of_birth,
        nic_number: data.nic_number,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      toast.success("Account created — they will be prompted to set a password on first login");
      onOpenChange(false);
      form.reset();
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New account</DialogTitle>
        </DialogHeader>
        <form onSubmit={form.handleSubmit((d) => mutation.mutate(d))} className="space-y-4">
          {/* Account type selector */}
          <div className="space-y-1.5">
            <Label>Account type *</Label>
            <div className="grid grid-cols-1 gap-2">
              {availableTypes.map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => {
                    form.setValue("account_type", t);
                    form.clearErrors();
                  }}
                  className={cn(
                    "flex flex-col items-start text-left px-3 py-2.5 rounded-md border text-sm transition-colors",
                    accountType === t
                      ? "border-primary bg-primary/5 text-foreground"
                      : "border-border text-muted-foreground hover:border-foreground/40 hover:text-foreground"
                  )}
                >
                  <span className="font-medium">{ACCOUNT_TYPE_LABELS[t].label}</span>
                  <span className="text-xs text-muted-foreground mt-0.5">
                    {ACCOUNT_TYPE_LABELS[t].hint}
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="u-email">Email *</Label>
            <Input id="u-email" type="email" {...form.register("email")} />
            {form.formState.errors.email && (
              <p className="text-xs text-destructive">{form.formState.errors.email.message}</p>
            )}
          </div>

          {/* Club picker — only for league/super admin creating club_staff */}
          {accountType === "club_staff" && !creatorIsClubAdmin && (
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
                          {c.name}
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
          )}

          {/* Personal details — required for all account types */}
          <div className="space-y-1.5">
            <Label htmlFor="full_name">Full name *</Label>
            <Input
              id="full_name"
              {...form.register("full_name")}
              placeholder="e.g. Kamal Perera"
            />
            {form.formState.errors.full_name && (
              <p className="text-xs text-destructive">
                {form.formState.errors.full_name.message}
              </p>
            )}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="date_of_birth">Date of birth *</Label>
            <Input id="date_of_birth" type="date" {...form.register("date_of_birth")} />
            {form.formState.errors.date_of_birth && (
              <p className="text-xs text-destructive">
                {form.formState.errors.date_of_birth.message}
              </p>
            )}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="nic_number">NIC number *</Label>
            <Input
              id="nic_number"
              {...form.register("nic_number")}
              placeholder="e.g. 901234567V"
            />
            {form.formState.errors.nic_number && (
              <p className="text-xs text-destructive">
                {form.formState.errors.nic_number.message}
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="tmp-pw">Temporary password *</Label>
            <Input
              id="tmp-pw"
              type="password"
              {...form.register("temporary_password")}
              placeholder="Min. 8 characters"
            />
            {form.formState.errors.temporary_password && (
              <p className="text-xs text-destructive">
                {form.formState.errors.temporary_password.message}
              </p>
            )}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Creating…" : "Create account"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Assign role dialog (super_admin only)
// ---------------------------------------------------------------------------

const assignRoleSchema = z
  .object({
    new_role: z.enum(["league_admin", "club_admin", "club_staff", "player"] as const),
    club_id: z.number().optional(),
    reason: z.string().min(1, "Reason is required"),
  })
  .superRefine((val, ctx) => {
    if (val.new_role === "club_admin" && !val.club_id) {
      ctx.addIssue({
        code: "custom",
        path: ["club_id"],
        message: "Club is required for club_admin role",
      });
    }
  });

type AssignRoleForm = z.infer<typeof assignRoleSchema>;

function AssignRoleDialog({
  user,
  open,
  onOpenChange,
}: {
  user: UserRead | null;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const queryClient = useQueryClient();

  const { data: clubs } = useQuery<ClubRead[]>({
    queryKey: ["clubs"],
    queryFn: clubsApi.list,
    enabled: open,
  });

  const form = useForm<AssignRoleForm>({
    resolver: zodResolver(assignRoleSchema),
    defaultValues: { new_role: "player", reason: "" },
  });

  const newRole = form.watch("new_role");

  const mutation = useMutation({
    mutationFn: (data: AssignRoleForm) => {
      const payload: AssignRoleRequest = {
        new_role: data.new_role,
        club_id: data.club_id ?? null,
        reason: data.reason,
      };
      return usersApi.assignRole(user!.id, payload);
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      const isStepDown = ["player", "club_staff"].includes(variables.new_role);
      toast.success(isStepDown ? "Role updated — all governance roles cleared" : "Role added successfully");
      // JWT-based delay notice: the affected user must re-login for their token to reflect the change
      toast.info(
        "The user must log out and back in for role changes to take effect in their session.",
        { duration: 7000 }
      );
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
          {user && (
            <p className="text-sm text-muted-foreground pt-1">{user.email}</p>
          )}
        </DialogHeader>

        {user && (
          <div className="-mt-2 pb-1 space-y-1">
            {user.governance_roles && user.governance_roles.length > 0 && (
              <p className="text-xs text-muted-foreground">
                Current governance roles:{" "}
                <span className="font-medium">
                  {user.governance_roles.map((g) => g.role.replace(/_/g, " ")).join(", ")}
                </span>
              </p>
            )}
            <p className="text-xs text-amber-600 dark:text-amber-400">
              Governance roles are <strong>additive</strong> — assigning league_admin keeps existing club_admin.
              Assigning player/club_staff clears all governance roles.
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
                <Select onValueChange={field.onChange} value={field.value}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(
                      ["league_admin", "club_admin", "club_staff", "player"] as const
                    ).map((r) => (
                      <SelectItem key={r} value={r}>
                        {r.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </div>

          {newRole === "club_admin" && (
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
                          {c.name}
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
          )}

          <div className="space-y-1.5">
            <Label htmlFor="ar-reason">Reason *</Label>
            <Input
              id="ar-reason"
              {...form.register("reason")}
              placeholder="e.g. Elected club president at AGM 2026"
            />
            {form.formState.errors.reason && (
              <p className="text-xs text-destructive">
                {form.formState.errors.reason.message}
              </p>
            )}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
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
// Role tags — shows identity (member_type) + governance role as separate badges
// ---------------------------------------------------------------------------

function RoleCell({ user }: { user: UserRead }) {
  // governance_roles lists all stacked governance roles (club_admin + league_admin etc.)
  const govRoles = user.governance_roles ?? [];

  return (
    <div className="flex items-center gap-1 flex-wrap">
      {/* Identity tag — the person's base club-membership type */}
      {user.member_type && <StatusBadge status={user.member_type} />}

      {/* All active governance role tags */}
      {govRoles.map((gr, i) => (
        <StatusBadge key={`${gr.role}-${i}`} status={gr.role} />
      ))}

      {/* Fallback: no member_type AND no governance roles → show role directly */}
      {!user.member_type && govRoles.length === 0 && (
        <StatusBadge status={user.role} />
      )}
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
  const [hardDeleteTarget, setHardDeleteTarget] = useState<UserRead | null>(null);
  const [restoreTarget, setRestoreTarget] = useState<UserRead | null>(null);
  const [actionTarget, setActionTarget] = useState<{
    user: UserRead;
    action: AccountAction;
    label: string;
  } | null>(null);
  const queryClient = useQueryClient();
  const { isSuperAdmin, isLeagueLevel } = useCurrentUser();

  // Active users
  const {
    data: activeUsers,
    isLoading: activeLoading,
    error: activeError,
    refetch: refetchActive,
  } = useQuery<UserRead[]>({
    queryKey: ["users"],
    queryFn: () => usersApi.list(false),
  });

  // Deleted users (super_admin, loaded when tab is "deleted")
  const {
    data: deletedUsers,
    isLoading: deletedLoading,
    error: deletedError,
    refetch: refetchDeleted,
  } = useQuery<UserRead[]>({
    queryKey: ["users", "deleted"],
    queryFn: () => usersApi.list(true).then((all) => all.filter((u) => u.is_deleted)),
    enabled: isSuperAdmin && tab === "deleted",
  });

  // Account actions (activate / deactivate / reset_password / soft_delete)
  const actionMutation = useMutation({
    mutationFn: ({
      userId,
      action,
      reason,
    }: {
      userId: number;
      action: AccountAction;
      reason: string;
    }) => usersApi.accountAction(userId, { action, reason }),
    onSuccess: (_, { action }) => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      const labels: Record<AccountAction, string> = {
        activate: "activated",
        deactivate: "deactivated",
        soft_delete: "deleted",
        reset_password: "password reset — a temporary password has been sent",
        update_mobile: "mobile updated",
      };
      toast.success(`User ${labels[action]}`);
      setActionTarget(null);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  // Hard delete (permanent)
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

  // Restore
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

  // -----------------------------------------------------------------------
  // Render helpers
  // -----------------------------------------------------------------------

  const isLoading = tab === "active" ? activeLoading : deletedLoading;
  const error = tab === "active" ? activeError : deletedError;
  const refetch = tab === "active" ? refetchActive : refetchDeleted;
  const users = tab === "active" ? activeUsers : deletedUsers;

  return (
    <div>
      <PageHeader
        title="Users"
        description="All accounts in the system"
        action={
          isLeagueLevel && tab === "active" ? (
            <Button size="sm" onClick={() => setCreateOpen(true)} className="gap-1.5">
              <Plus className="h-4 w-4" />
              New user
            </Button>
          ) : undefined
        }
      />

      {/* Tabs — only super_admin sees the Deleted tab */}
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

      {isLoading ? (
        <DataTableSkeleton columns={6} />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : !users?.length ? (
        <EmptyState
          title={tab === "deleted" ? "No deleted users" : "No users"}
          icon={<Users className="h-6 w-6" />}
          action={
            isLeagueLevel && tab === "active"
              ? { label: "Create user", onClick: () => setCreateOpen(true) }
              : undefined
          }
        />
      ) : tab === "active" ? (
        /* ---- Active users table ---- */
        <div className="rounded-lg border border-border overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Email</TableHead>
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
              {users.map((user) => (
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
                  <TableCell>
                    <RoleCell user={user} />
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {user.club_id ? `Club ${user.club_id}` : "—"}
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={user.is_active ? "active" : "inactive"} />
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {user.last_login_at ? formatRelative(user.last_login_at) : "Never"}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatDate(user.created_at)}
                  </TableCell>
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-7 w-7">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        {user.is_active ? (
                          <DropdownMenuItem
                            onClick={() =>
                              setActionTarget({
                                user,
                                action: "deactivate",
                                label: "Deactivate user",
                              })
                            }
                          >
                            Deactivate
                          </DropdownMenuItem>
                        ) : (
                          <DropdownMenuItem
                            onClick={() =>
                              setActionTarget({
                                user,
                                action: "activate",
                                label: "Activate user",
                              })
                            }
                          >
                            Activate
                          </DropdownMenuItem>
                        )}
                        <DropdownMenuItem
                          onClick={() =>
                            setActionTarget({
                              user,
                              action: "reset_password",
                              label: "Reset password",
                            })
                          }
                        >
                          Reset password
                        </DropdownMenuItem>
                        {isSuperAdmin && (
                          <>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              onClick={() => setAssignRoleTarget(user)}
                            >
                              Assign role
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              className="text-destructive focus:text-destructive"
                              onClick={() =>
                                setActionTarget({
                                  user,
                                  action: "soft_delete",
                                  label: "Delete user",
                                })
                              }
                            >
                              Delete user
                            </DropdownMenuItem>
                          </>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                  <TableCell className="w-6">
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : (
        /* ---- Deleted users table (super_admin) ---- */
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
                    <span className="font-medium text-sm line-through text-muted-foreground">
                      {user.email}
                    </span>
                  </TableCell>
                  <TableCell>
                    <RoleCell user={user} />
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {user.club_id ? `Club ${user.club_id}` : "—"}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatDate(user.created_at)}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 gap-1.5 text-xs"
                        onClick={() => setRestoreTarget(user)}
                      >
                        <RefreshCw className="h-3 w-3" />
                        Restore
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 gap-1.5 text-xs text-destructive hover:text-destructive"
                        onClick={() => setHardDeleteTarget(user)}
                      >
                        <Trash2 className="h-3 w-3" />
                        Delete forever
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
          onConfirm={(reason) =>
            actionMutation.mutate({
              userId: actionTarget.user.id,
              action: actionTarget.action,
              reason: reason ?? "",
            })
          }
        />
      )}

      {restoreTarget && (
        <ConfirmDialog
          open
          onOpenChange={(v) => { if (!v) setRestoreTarget(null); }}
          title="Restore user"
          description={`Restore ${restoreTarget.email}? The account will be re-activated. Reset their password afterwards so they can log in again.`}
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
          description={`This will permanently delete ${hardDeleteTarget.email} and remove their Cognito account. This cannot be undone.`}
          confirmLabel="Delete forever"
          destructive
          loading={hardDeleteMutation.isPending}
          onConfirm={() => hardDeleteMutation.mutate(hardDeleteTarget.id)}
        />
      )}
    </div>
  );
}
