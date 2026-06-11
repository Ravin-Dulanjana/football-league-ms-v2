"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { AlertTriangle, Lock, Pencil, Plus, ScrollText, Trash2 } from "lucide-react";

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
import { cn, formatDate } from "@/lib/utils";
import type { SeasonRead, SeasonStatus } from "@/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STATUS_ORDER: SeasonStatus[] = ["draft", "open", "active", "closed", "archived"];

const STATUS_INFO: Record<SeasonStatus, { label: string; hint: string }> = {
  draft: { label: "Draft", hint: "Not yet opened. Dates can still be changed." },
  open: {
    label: "Open",
    hint: "Registration window is open. Clubs can register their players.",
  },
  active: {
    label: "Active",
    hint: "Season is running. Rosters are locked — no additions or removals.",
  },
  closed: {
    label: "Closed",
    hint: "Season ended. Clubs may release players or invite new ones.",
  },
  archived: { label: "Archived", hint: "Fully complete — no further changes." },
};

// ---------------------------------------------------------------------------
// Create dialog
// ---------------------------------------------------------------------------

const createSchema = z
  .object({
    name: z.string().min(1, "Name is required"),
    year: z.number().int().min(2020).max(2100),
    registration_open_at: z.string().min(1, "Required"),
    registration_close_at: z.string().min(1, "Required"),
    season_end_date: z.string().optional(),
  })
  .superRefine((val, ctx) => {
    if (val.registration_close_at && val.registration_open_at) {
      if (new Date(val.registration_close_at) <= new Date(val.registration_open_at)) {
        ctx.addIssue({
          code: "custom",
          path: ["registration_close_at"],
          message: "Must be after registration opens",
        });
      }
    }
    if (val.season_end_date && val.registration_close_at) {
      if (new Date(val.season_end_date) <= new Date(val.registration_close_at)) {
        ctx.addIssue({
          code: "custom",
          path: ["season_end_date"],
          message: "Must be after registration closes",
        });
      }
    }
  });

type CreateForm = z.infer<typeof createSchema>;

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
      season_end_date: "",
    },
  });

  const mutation = useMutation({
    mutationFn: (data: CreateForm) =>
      seasonsApi.create({
        name: data.name,
        year: data.year,
        registration_open_at: data.registration_open_at,
        registration_close_at: data.registration_close_at,
        season_end_date: data.season_end_date || undefined,
      }),
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
        <p className="text-sm text-muted-foreground -mt-2">
          Set three key dates: when clubs can start registering players, when registration closes,
          and when the season roughly ends.
        </p>
        <form onSubmit={form.handleSubmit((d) => mutation.mutate(d))} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="s-name">Season name *</Label>
              <Input id="s-name" {...form.register("name")} placeholder="e.g. Premier 2026" />
              {form.formState.errors.name && (
                <p className="text-xs text-destructive">{form.formState.errors.name.message}</p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="s-year">Year *</Label>
              <Input
                id="s-year"
                type="number"
                {...form.register("year", { valueAsNumber: true })}
              />
              {form.formState.errors.year && (
                <p className="text-xs text-destructive">{form.formState.errors.year.message}</p>
              )}
            </div>
          </div>

          <div className="space-y-3 rounded-md border border-border p-3">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Registration window
            </p>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="s-open">Opens *</Label>
                <Input id="s-open" type="datetime-local" {...form.register("registration_open_at")} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="s-close">Closes *</Label>
                <Input
                  id="s-close"
                  type="datetime-local"
                  {...form.register("registration_close_at")}
                />
                {form.formState.errors.registration_close_at && (
                  <p className="text-xs text-destructive">
                    {form.formState.errors.registration_close_at.message}
                  </p>
                )}
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              Clubs can register players between these dates.
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="s-end">Season end date (approximate)</Label>
            <Input id="s-end" type="datetime-local" {...form.register("season_end_date")} />
            {form.formState.errors.season_end_date && (
              <p className="text-xs text-destructive">
                {form.formState.errors.season_end_date.message}
              </p>
            )}
            <p className="text-xs text-muted-foreground">
              After this date the season moves to Closed — clubs can release or sign players.
            </p>
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

const editSchema = z
  .object({
    name: z.string().min(1, "Name is required"),
    registration_open_at: z.string().min(1, "Required"),
    registration_close_at: z.string().min(1, "Required"),
    season_end_date: z.string().optional(),
    status: z.enum(["draft", "open", "active", "closed", "archived"] as const),
  })
  .superRefine((val, ctx) => {
    if (val.registration_close_at && val.registration_open_at) {
      if (new Date(val.registration_close_at) <= new Date(val.registration_open_at)) {
        ctx.addIssue({
          code: "custom",
          path: ["registration_close_at"],
          message: "Must be after registration opens",
        });
      }
    }
    if (val.season_end_date && val.registration_close_at) {
      if (new Date(val.season_end_date) <= new Date(val.registration_close_at)) {
        ctx.addIssue({
          code: "custom",
          path: ["season_end_date"],
          message: "Must be after registration closes",
        });
      }
    }
  });

type EditForm = z.infer<typeof editSchema>;

// Map status → allowed next statuses (mirrors backend VALID_TRANSITIONS)
const NEXT_STATUSES: Record<SeasonStatus, SeasonStatus[]> = {
  draft: ["draft", "open"],
  open: ["open", "active"],
  active: ["active", "closed"],
  closed: ["closed", "archived"],
  archived: ["archived"],
};

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
      season_end_date: season.season_end_date ? season.season_end_date.slice(0, 16) : "",
      status: season.status,
    },
  });

  const allowedStatuses = NEXT_STATUSES[season.status];

  const mutation = useMutation({
    mutationFn: (data: EditForm) =>
      seasonsApi.update(season.id, {
        name: data.name,
        registration_open_at: data.registration_open_at,
        registration_close_at: data.registration_close_at,
        season_end_date: data.season_end_date || null,
        status: data.status,
      }),
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
          <DialogTitle>Edit season — {season.name}</DialogTitle>
        </DialogHeader>
        <form onSubmit={form.handleSubmit((d) => mutation.mutate(d))} className="space-y-4">
          <div className="space-y-1.5">
            <Label>Season name *</Label>
            <Input {...form.register("name")} />
          </div>
          <div className="space-y-3 rounded-md border border-border p-3">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Registration window
            </p>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Opens *</Label>
                <Input type="datetime-local" {...form.register("registration_open_at")} />
              </div>
              <div className="space-y-1.5">
                <Label>Closes *</Label>
                <Input type="datetime-local" {...form.register("registration_close_at")} />
                {form.formState.errors.registration_close_at && (
                  <p className="text-xs text-destructive">
                    {form.formState.errors.registration_close_at.message}
                  </p>
                )}
              </div>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>Season end date (approximate)</Label>
            <Input type="datetime-local" {...form.register("season_end_date")} />
            {form.formState.errors.season_end_date && (
              <p className="text-xs text-destructive">
                {form.formState.errors.season_end_date.message}
              </p>
            )}
          </div>
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
                    {allowedStatuses.map((s) => (
                      <SelectItem key={s} value={s}>
                        <span className="capitalize">{STATUS_INFO[s].label}</span>
                        <span className="ml-2 text-xs text-muted-foreground">
                          — {STATUS_INFO[s].hint}
                        </span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
            {season.status === "open" && (
              <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">
                Moving to <strong>Active</strong> locks all rosters — no further registration
                changes until season ends.
              </p>
            )}
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
// Delete confirmation — double-confirm
// ---------------------------------------------------------------------------

function DeleteSeasonDialog({
  season,
  onOpenChange,
}: {
  season: SeasonRead;
  onOpenChange: (v: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [step, setStep] = useState<1 | 2>(1);
  const [nameConfirm, setNameConfirm] = useState("");

  const mutation = useMutation({
    mutationFn: () => seasonsApi.delete(season.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["seasons"] });
      toast.success(`Season "${season.name}" deleted`);
      onOpenChange(false);
    },
    onError: (err: Error) => {
      toast.error(err.message);
      onOpenChange(false);
    },
  });

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-5 w-5" />
            Delete season
          </DialogTitle>
        </DialogHeader>

        {step === 1 ? (
          <>
            <div className="space-y-3 text-sm">
              <p>
                You are about to permanently delete{" "}
                <strong>&quot;{season.name}&quot;</strong>.
              </p>
              <p className="text-muted-foreground">
                This will also delete all registration requests and season-roster entries
                for this season. This cannot be undone.
              </p>
              <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-xs">
                Only <strong>Draft</strong> and <strong>Archived</strong> seasons can be deleted.
                Active or closed seasons with live data must be archived first.
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
              <Button variant="destructive" onClick={() => setStep(2)}>
                I understand — continue
              </Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <div className="space-y-3 text-sm">
              <p>
                Type <strong>{season.name}</strong> to confirm deletion:
              </p>
              <Input
                value={nameConfirm}
                onChange={(e) => setNameConfirm(e.target.value)}
                placeholder={season.name}
                className="font-mono"
              />
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => { setStep(1); setNameConfirm(""); }}>
                Back
              </Button>
              <Button
                variant="destructive"
                disabled={nameConfirm !== season.name || mutation.isPending}
                onClick={() => mutation.mutate()}
              >
                {mutation.isPending ? "Deleting…" : "Delete forever"}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Season card — detailed view
// ---------------------------------------------------------------------------

function SeasonTimeline({ season }: { season: SeasonRead }) {
  const statuses = STATUS_ORDER.filter((s) => s !== "archived") as SeasonStatus[];
  const currentIdx = statuses.indexOf(season.status);

  return (
    <div className="flex items-center gap-1">
      {statuses.map((s, i) => (
        <div key={s} className="flex items-center gap-1">
          <div
            className={cn(
              "h-2 w-2 rounded-full",
              i < currentIdx
                ? "bg-primary"
                : i === currentIdx
                ? "bg-primary ring-2 ring-primary/30"
                : "bg-muted-foreground/20"
            )}
            title={STATUS_INFO[s as SeasonStatus].label}
          />
          {i < statuses.length - 1 && (
            <div
              className={cn(
                "h-0.5 w-4",
                i < currentIdx ? "bg-primary" : "bg-muted-foreground/20"
              )}
            />
          )}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function SeasonsPage() {
  const [createOpen, setCreateOpen] = useState(false);
  const [editSeason, setEditSeason] = useState<SeasonRead | null>(null);
  const [deleteSeason, setDeleteSeason] = useState<SeasonRead | null>(null);
  const { isLeagueLevel } = useCurrentUser();

  const { data: seasons, isLoading, error, refetch } = useQuery<SeasonRead[]>({
    queryKey: ["seasons"],
    queryFn: seasonsApi.list,
  });

  const canDelete = (s: SeasonRead) =>
    isLeagueLevel && (s.status === "draft" || s.status === "archived");

  return (
    <div>
      <PageHeader
        title="Seasons"
        description="Manage league seasons, registration windows, and season lifecycle"
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
        <DataTableSkeleton columns={7} />
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
                <TableHead>Reg. opens</TableHead>
                <TableHead>Reg. closes</TableHead>
                <TableHead>Season ends</TableHead>
                {isLeagueLevel && <TableHead />}
              </TableRow>
            </TableHeader>
            <TableBody>
              {seasons.map((season) => (
                <TableRow key={season.id} className="hover:bg-muted/50">
                  <TableCell>
                    <div className="flex flex-col gap-1">
                      <span className="font-medium">{season.name}</span>
                      <SeasonTimeline season={season} />
                    </div>
                  </TableCell>
                  <TableCell>{season.year}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1.5">
                      <StatusBadge status={season.status} />
                      {season.is_locked && (
                        <Lock className="h-3 w-3 text-amber-500" />
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatDate(season.registration_open_at)}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatDate(season.registration_close_at)}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {season.season_end_date ? formatDate(season.season_end_date) : "—"}
                  </TableCell>
                  {isLeagueLevel && (
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          onClick={() => setEditSeason(season)}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        {canDelete(season) && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 text-destructive hover:text-destructive"
                            onClick={() => setDeleteSeason(season)}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Season lifecycle explanation */}
      <div className="mt-6 rounded-lg border border-border bg-muted/30 p-4">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
          Season lifecycle
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
          {(["draft", "open", "active", "closed"] as SeasonStatus[]).map((s) => (
            <div key={s} className="space-y-0.5">
              <div className="flex items-center gap-1.5">
                <StatusBadge status={s} />
                {s === "active" && <Lock className="h-3 w-3 text-amber-500" />}
              </div>
              <p className="text-xs text-muted-foreground">{STATUS_INFO[s].hint}</p>
            </div>
          ))}
        </div>
      </div>

      <CreateSeasonDialog open={createOpen} onOpenChange={setCreateOpen} />
      {editSeason && (
        <EditSeasonDialog
          season={editSeason}
          onOpenChange={(v) => { if (!v) setEditSeason(null); }}
        />
      )}
      {deleteSeason && (
        <DeleteSeasonDialog
          season={deleteSeason}
          onOpenChange={(v) => { if (!v) setDeleteSeason(null); }}
        />
      )}
    </div>
  );
}
