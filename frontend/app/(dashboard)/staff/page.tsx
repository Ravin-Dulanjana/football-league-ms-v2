"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Plus, Trash2, UserSquare2 } from "lucide-react";

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
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { staffApi, clubsApi, seasonsApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { ClubRead, ClubStaffRead, SeasonRead } from "@/types";

// ---------------------------------------------------------------------------
// Create staff dialog
// ---------------------------------------------------------------------------

const schema = z.object({
  club_id: z.number().int().positive("Select a club"),
  season_id: z.number().int().positive("Select a season"),
  full_name: z.string().min(1, "Full name is required"),
  role: z.string().min(1, "Role is required"),
});

type FormData = z.infer<typeof schema>;

function AddStaffDialog({
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
  const { data: seasons } = useQuery<SeasonRead[]>({
    queryKey: ["seasons"],
    queryFn: seasonsApi.list,
    enabled: open,
  });

  const form = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { club_id: 0, season_id: 0, full_name: "", role: "" },
  });

  const mutation = useMutation({
    mutationFn: (data: FormData) =>
      staffApi.create({
        club_id: data.club_id,
        season_id: data.season_id,
        full_name: data.full_name,
        role: data.role,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["staff"] });
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
              <p className="text-xs text-destructive">{form.formState.errors.club_id.message}</p>
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
                        {s.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
            {form.formState.errors.season_id && (
              <p className="text-xs text-destructive">{form.formState.errors.season_id.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="sf-name">Full name *</Label>
            <Input id="sf-name" {...form.register("full_name")} placeholder="e.g. Nimal Perera" />
            {form.formState.errors.full_name && (
              <p className="text-xs text-destructive">{form.formState.errors.full_name.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="sf-role">Role *</Label>
            <Input id="sf-role" {...form.register("role")} placeholder="e.g. Head Coach" />
            {form.formState.errors.role && (
              <p className="text-xs text-destructive">{form.formState.errors.role.message}</p>
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

export default function StaffPage() {
  const [addOpen, setAddOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ClubStaffRead | null>(null);
  const queryClient = useQueryClient();
  const { isAnyAdmin } = useCurrentUser();

  const { data: staff, isLoading, error, refetch } = useQuery<ClubStaffRead[]>({
    queryKey: ["staff"],
    queryFn: () => staffApi.list(),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => staffApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["staff"] });
      toast.success("Staff member removed");
      setDeleteTarget(null);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <div>
      <PageHeader
        title="Support staff"
        description="Club support staff registered per season"
        action={
          isAnyAdmin ? (
            <Button size="sm" onClick={() => setAddOpen(true)} className="gap-1.5">
              <Plus className="h-4 w-4" />
              Add staff
            </Button>
          ) : undefined
        }
      />

      {isLoading ? (
        <DataTableSkeleton columns={5} />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : !staff?.length ? (
        <EmptyState
          title="No support staff"
          description="Add support staff to track coaching and management per season"
          icon={<UserSquare2 className="h-6 w-6" />}
          action={
            isAnyAdmin ? { label: "Add staff", onClick: () => setAddOpen(true) } : undefined
          }
        />
      ) : (
        <div className="rounded-lg border border-border overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Club</TableHead>
                <TableHead>Season</TableHead>
                <TableHead>Added</TableHead>
                {isAnyAdmin && <TableHead />}
              </TableRow>
            </TableHeader>
            <TableBody>
              {staff.map((s) => (
                <TableRow key={s.id} className="hover:bg-muted/50">
                  <TableCell className="font-medium">{s.full_name}</TableCell>
                  <TableCell className="text-sm">{s.role}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">Club {s.club_id}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    Season {s.season_id}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatDate(s.created_at)}
                  </TableCell>
                  {isAnyAdmin && (
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-muted-foreground hover:text-destructive"
                        onClick={() => setDeleteTarget(s)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <AddStaffDialog open={addOpen} onOpenChange={setAddOpen} />

      {deleteTarget && (
        <ConfirmDialog
          open
          onOpenChange={(v) => { if (!v) setDeleteTarget(null); }}
          title="Remove staff member?"
          description={`Remove ${deleteTarget.full_name} (${deleteTarget.role}) from this season's roster?`}
          confirmLabel="Remove"
          destructive
          loading={deleteMutation.isPending}
          onConfirm={() => deleteMutation.mutate(deleteTarget.id)}
        />
      )}
    </div>
  );
}
