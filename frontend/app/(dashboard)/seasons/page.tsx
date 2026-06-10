"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Lock, LockOpen, Pencil, Plus, ScrollText } from "lucide-react";

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
  DataTableSkeleton,
  EmptyState,
  ErrorState,
  PageHeader,
} from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { seasonsApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { SeasonRead, SeasonStatus } from "@/types";

// ---------------------------------------------------------------------------
// Schemas
// ---------------------------------------------------------------------------

const createSchema = z.object({
  name: z.string().min(1, "Name is required"),
  year: z.number().int().min(2020).max(2100),
  registration_open_at: z.string().min(1, "Required"),
  registration_close_at: z.string().min(1, "Required"),
});

const editSchema = z.object({
  name: z.string().min(1, "Name is required"),
  registration_open_at: z.string().min(1, "Required"),
  registration_close_at: z.string().min(1, "Required"),
  status: z.enum(["draft", "open", "closed", "archived"]),
  is_locked: z.boolean(),
});

type CreateForm = z.infer<typeof createSchema>;
type EditForm = z.infer<typeof editSchema>;

// ---------------------------------------------------------------------------
// Create dialog
// ---------------------------------------------------------------------------

function CreateSeasonDialog({
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
      name: "",
      year: new Date().getFullYear(),
      registration_open_at: "",
      registration_close_at: "",
    },
  });

  const mutation = useMutation({
    mutationFn: (data: CreateForm) => seasonsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["seasons"] });
      toast.success("Season created");
      onOpenChange(false);
      form.reset();
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New season</DialogTitle>
        </DialogHeader>
        <form onSubmit={form.handleSubmit((d) => mutation.mutate(d))} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="s-name">Season name *</Label>
            <Input id="s-name" {...form.register("name")} placeholder="e.g. Premier League 2025" />
            {form.formState.errors.name && (
              <p className="text-xs text-destructive">{form.formState.errors.name.message}</p>
            )}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="s-year">Year *</Label>
            <Input id="s-year" type="number" {...form.register("year", { valueAsNumber: true })} />
            {form.formState.errors.year && (
              <p className="text-xs text-destructive">{form.formState.errors.year.message}</p>
            )}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="s-open">Registration opens *</Label>
              <Input id="s-open" type="datetime-local" {...form.register("registration_open_at")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="s-close">Registration closes *</Label>
              <Input id="s-close" type="datetime-local" {...form.register("registration_close_at")} />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Creating…" : "Create season"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Edit dialog
// ---------------------------------------------------------------------------

function EditSeasonDialog({
  season,
  onOpenChange,
}: {
  season: SeasonRead;
  onOpenChange: (v: boolean) => void;
}) {
  const queryClient = useQueryClient();

  const form = useForm<EditForm>({
    resolver: zodResolver(editSchema),
    defaultValues: {
      name: season.name,
      registration_open_at: season.registration_open_at.slice(0, 16),
      registration_close_at: season.registration_close_at.slice(0, 16),
      status: season.status,
      is_locked: season.is_locked,
    },
  });

  const mutation = useMutation({
    mutationFn: (data: EditForm) => seasonsApi.update(season.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["seasons"] });
      toast.success("Season updated");
      onOpenChange(false);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit season</DialogTitle>
        </DialogHeader>
        <form onSubmit={form.handleSubmit((d) => mutation.mutate(d))} className="space-y-4">
          <div className="space-y-1.5">
            <Label>Season name *</Label>
            <Input {...form.register("name")} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Registration opens *</Label>
              <Input type="datetime-local" {...form.register("registration_open_at")} />
            </div>
            <div className="space-y-1.5">
              <Label>Registration closes *</Label>
              <Input type="datetime-local" {...form.register("registration_close_at")} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Status</Label>
              <Controller
                control={form.control}
                name="status"
                render={({ field }) => (
                  <Select onValueChange={field.onChange} value={field.value}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {(["draft", "open", "closed", "archived"] as SeasonStatus[]).map((s) => (
                        <SelectItem key={s} value={s} className="capitalize">
                          {s}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Lock</Label>
              <Controller
                control={form.control}
                name="is_locked"
                render={({ field }) => (
                  <Select
                    onValueChange={(v) => field.onChange(v === "true")}
                    value={String(field.value)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="false">Unlocked</SelectItem>
                      <SelectItem value="true">Locked</SelectItem>
                    </SelectContent>
                  </Select>
                )}
              />
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
// Main page
// ---------------------------------------------------------------------------

export default function SeasonsPage() {
  const [createOpen, setCreateOpen] = useState(false);
  const [editSeason, setEditSeason] = useState<SeasonRead | null>(null);
  const { isLeagueLevel } = useCurrentUser();

  const { data: seasons, isLoading, error, refetch } = useQuery<SeasonRead[]>({
    queryKey: ["seasons"],
    queryFn: seasonsApi.list,
  });

  return (
    <div>
      <PageHeader
        title="Seasons"
        description="Manage league seasons and registration windows"
        action={
          isLeagueLevel ? (
            <Button size="sm" onClick={() => setCreateOpen(true)} className="gap-1.5">
              <Plus className="h-4 w-4" />
              New season
            </Button>
          ) : undefined
        }
      />

      {isLoading ? (
        <DataTableSkeleton columns={6} />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : !seasons?.length ? (
        <EmptyState
          title="No seasons yet"
          description="Create the first season to open registrations"
          icon={<ScrollText className="h-6 w-6" />}
          action={
            isLeagueLevel
              ? { label: "Create season", onClick: () => setCreateOpen(true) }
              : undefined
          }
        />
      ) : (
        <div className="rounded-lg border border-border overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Year</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Lock</TableHead>
                <TableHead>Open</TableHead>
                <TableHead>Close</TableHead>
                {isLeagueLevel && <TableHead />}
              </TableRow>
            </TableHeader>
            <TableBody>
              {seasons.map((season) => (
                <TableRow key={season.id} className="hover:bg-muted/50">
                  <TableCell className="font-medium">{season.name}</TableCell>
                  <TableCell>{season.year}</TableCell>
                  <TableCell>
                    <StatusBadge status={season.status} />
                  </TableCell>
                  <TableCell>
                    {season.is_locked ? (
                      <Lock className="h-4 w-4 text-amber-500" />
                    ) : (
                      <LockOpen className="h-4 w-4 text-green-500" />
                    )}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatDate(season.registration_open_at)}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatDate(season.registration_close_at)}
                  </TableCell>
                  {isLeagueLevel && (
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => setEditSeason(season)}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <CreateSeasonDialog open={createOpen} onOpenChange={setCreateOpen} />
      {editSeason && (
        <EditSeasonDialog
          season={editSeason}
          onOpenChange={(v) => { if (!v) setEditSeason(null); }}
        />
      )}
    </div>
  );
}
