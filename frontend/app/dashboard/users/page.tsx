"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm, Controller } from "react-hook-form";
import { useRouter } from "next/navigation";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { ChevronRight, MoreHorizontal, Plus, Users } from "lucide-react";

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
import { formatDate, formatRelative } from "@/lib/utils";
import type { AccountAction, ClubRead, UserRead, UserRole } from "@/types";

// ---------------------------------------------------------------------------
// Create user dialog
// ---------------------------------------------------------------------------

const createSchema = z
  .object({
    email: z.string().email("Invalid email"),
    role: z.enum(["super_admin", "league_admin", "club_admin", "player"] as const),
    club_id: z.number().optional(),
    temporary_password: z.string().min(8, "At least 8 characters"),
    full_name: z.string().optional(),
    date_of_birth: z.string().optional(),
    nic_number: z.string().optional(),
  })
  .superRefine((val, ctx) => {
    if (val.role === "player") {
      if (!val.full_name?.trim()) {
        ctx.addIssue({ code: "custom", path: ["full_name"], message: "Required for players" });
      }
      if (!val.date_of_birth) {
        ctx.addIssue({ code: "custom", path: ["date_of_birth"], message: "Required for players" });
      }
      if (!val.nic_number?.trim()) {
        ctx.addIssue({ code: "custom", path: ["nic_number"], message: "Required for players" });
      }
    }
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

  const { data: clubs } = useQuery<ClubRead[]>({
    queryKey: ["clubs"],
    queryFn: clubsApi.list,
    enabled: open,
  });

  const form = useForm<CreateForm>({
    resolver: zodResolver(createSchema),
    defaultValues: {
      email: "",
      role: "club_admin",
      temporary_password: "",
      full_name: "",
      date_of_birth: "",
      nic_number: "",
    },
  });

  const role = form.watch("role");

  const mutation = useMutation({
    mutationFn: (data: CreateForm) =>
      usersApi.create({
        email: data.email,
        role: data.role,
        club_id: data.role === "club_admin" ? data.club_id : undefined,
        temporary_password: data.temporary_password,
        ...(data.role === "player" && {
          full_name: data.full_name,
          date_of_birth: data.date_of_birth,
          nic_number: data.nic_number,
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      toast.success("User created — they will be prompted to change their password on first login");
      onOpenChange(false);
      form.reset();
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{role === "player" ? "New player account" : "New user"}</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={form.handleSubmit((d) => mutation.mutate(d))}
          className="space-y-4"
        >
          <div className="space-y-1.5">
            <Label htmlFor="u-email">Email *</Label>
            <Input id="u-email" type="email" {...form.register("email")} />
            {form.formState.errors.email && (
              <p className="text-xs text-destructive">{form.formState.errors.email.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label>Role *</Label>
            <Controller
              control={form.control}
              name="role"
              render={({ field }) => (
                <Select onValueChange={field.onChange} value={field.value}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(
                      ["super_admin", "league_admin", "club_admin", "player"] as UserRole[]
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

          {role === "club_admin" && (
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
            </div>
          )}

          {role === "player" && (
            <>
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
            </>
          )}

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
              {mutation.isPending ? "Creating…" : "Create user"}
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

export default function UsersPage() {
  const router = useRouter();
  const [createOpen, setCreateOpen] = useState(false);
  const [actionTarget, setActionTarget] = useState<{
    user: UserRead;
    action: AccountAction;
    label: string;
  } | null>(null);
  const queryClient = useQueryClient();
  const { isSuperAdmin, isLeagueLevel } = useCurrentUser();

  const { data: users, isLoading, error, refetch } = useQuery<UserRead[]>({
    queryKey: ["users"],
    queryFn: () => usersApi.list(),
  });

  const actionMutation = useMutation({
    mutationFn: ({ userId, action, reason }: { userId: number; action: AccountAction; reason: string }) =>
      usersApi.accountAction(userId, { action, reason }),
    onSuccess: (_, { action }) => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      const labels: Record<AccountAction, string> = {
        activate: "activated",
        deactivate: "deactivated",
        soft_delete: "deleted",
        reset_password: "password reset",
        update_mobile: "mobile updated",
      };
      toast.success(`User ${labels[action]}`);
      setActionTarget(null);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <div>
      <PageHeader
        title="Users"
        description="All accounts in the system"
        action={
          isLeagueLevel ? (
            <Button size="sm" onClick={() => setCreateOpen(true)} className="gap-1.5">
              <Plus className="h-4 w-4" />
              New user
            </Button>
          ) : undefined
        }
      />

      {isLoading ? (
        <DataTableSkeleton columns={6} />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : !users?.length ? (
        <EmptyState
          title="No users"
          icon={<Users className="h-6 w-6" />}
          action={
            isLeagueLevel
              ? { label: "Create user", onClick: () => setCreateOpen(true) }
              : undefined
          }
        />
      ) : (
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
                    <StatusBadge status={user.role} />
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
                              setActionTarget({ user, action: "deactivate", label: "Deactivate user" })
                            }
                          >
                            Deactivate
                          </DropdownMenuItem>
                        ) : (
                          <DropdownMenuItem
                            onClick={() =>
                              setActionTarget({ user, action: "activate", label: "Activate user" })
                            }
                          >
                            Activate
                          </DropdownMenuItem>
                        )}
                        <DropdownMenuItem
                          onClick={() =>
                            setActionTarget({ user, action: "reset_password", label: "Reset password" })
                          }
                        >
                          Reset password
                        </DropdownMenuItem>
                        {isSuperAdmin && (
                          <>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              className="text-destructive focus:text-destructive"
                              onClick={() =>
                                setActionTarget({ user, action: "soft_delete", label: "Delete user" })
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
      )}

      <CreateUserDialog open={createOpen} onOpenChange={setCreateOpen} />

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
    </div>
  );
}
