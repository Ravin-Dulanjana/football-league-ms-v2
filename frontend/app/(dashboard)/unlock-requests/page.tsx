"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Check, Key, Plus, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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
import { unlockRequestsApi, clubsApi, seasonsApi } from "@/lib/api";
import { formatRelative } from "@/lib/utils";
import type { ClubRead, SeasonRead, UnlockRequestRead } from "@/types";

// ---------------------------------------------------------------------------
// Create dialog
// ---------------------------------------------------------------------------

const schema = z.object({
  club_id: z.number().int().positive("Select a club"),
  season_id: z.number().int().positive("Select a season"),
  reason: z.string().min(10, "Please provide a reason (min. 10 characters)"),
});

type FormData = z.infer<typeof schema>;

function CreateDialog({
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
    defaultValues: { club_id: 0, season_id: 0, reason: "" },
  });

  const mutation = useMutation({
    mutationFn: (data: FormData) => unlockRequestsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["unlock-requests"] });
      toast.success("Unlock request submitted");
      onOpenChange(false);
      form.reset();
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Request season unlock</DialogTitle>
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
            <Label htmlFor="ur-reason">Reason *</Label>
            <Textarea
              id="ur-reason"
              {...form.register("reason")}
              placeholder="Explain why the season lock needs to be lifted for your club"
              rows={3}
            />
            {form.formState.errors.reason && (
              <p className="text-xs text-destructive">{form.formState.errors.reason.message}</p>
            )}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Submitting…" : "Submit request"}
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

export default function UnlockRequestsPage() {
  const [createOpen, setCreateOpen] = useState(false);
  const [decideTarget, setDecideTarget] = useState<{
    id: number;
    decision: "approve" | "reject";
  } | null>(null);
  const queryClient = useQueryClient();
  const { isLeagueLevel, isClubAdmin } = useCurrentUser();

  const { data: requests, isLoading, error, refetch } = useQuery<UnlockRequestRead[]>({
    queryKey: ["unlock-requests"],
    queryFn: unlockRequestsApi.list,
  });

  const decideMutation = useMutation({
    mutationFn: ({ id, decision }: { id: number; decision: "approve" | "reject" }) =>
      unlockRequestsApi.decide(id, decision),
    onSuccess: (_, { decision }) => {
      queryClient.invalidateQueries({ queryKey: ["unlock-requests"] });
      toast.success(decision === "approve" ? "Request approved" : "Request rejected");
      setDecideTarget(null);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <div>
      <PageHeader
        title="Unlock requests"
        description="Requests to unlock a locked season for a club"
        action={
          isClubAdmin ? (
            <Button size="sm" onClick={() => setCreateOpen(true)} className="gap-1.5">
              <Plus className="h-4 w-4" />
              New request
            </Button>
          ) : undefined
        }
      />

      {isLoading ? (
        <DataTableSkeleton columns={6} />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : !requests?.length ? (
        <EmptyState
          title="No unlock requests"
          icon={<Key className="h-6 w-6" />}
          action={
            isClubAdmin
              ? { label: "New request", onClick: () => setCreateOpen(true) }
              : undefined
          }
        />
      ) : (
        <div className="rounded-lg border border-border overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Club</TableHead>
                <TableHead>Season</TableHead>
                <TableHead>Reason</TableHead>
                <TableHead>Approvals</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Submitted</TableHead>
                {isLeagueLevel && <TableHead />}
              </TableRow>
            </TableHeader>
            <TableBody>
              {requests.map((r) => (
                <TableRow key={r.id} className="hover:bg-muted/50">
                  <TableCell className="font-medium">Club {r.club_id}</TableCell>
                  <TableCell>Season {r.season_id}</TableCell>
                  <TableCell className="max-w-xs">
                    <p className="text-sm truncate">{r.reason}</p>
                  </TableCell>
                  <TableCell className="text-sm">{r.approval_count}</TableCell>
                  <TableCell>
                    <StatusBadge status={r.status} />
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatRelative(r.created_at)}
                  </TableCell>
                  {isLeagueLevel && r.status === "pending" && (
                    <TableCell>
                      <div className="flex gap-1">
                        <Button
                          variant="outline"
                          size="icon"
                          className="h-7 w-7 border-green-500 text-green-600 hover:bg-green-50"
                          onClick={() => setDecideTarget({ id: r.id, decision: "approve" })}
                        >
                          <Check className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="outline"
                          size="icon"
                          className="h-7 w-7 border-red-400 text-red-600 hover:bg-red-50"
                          onClick={() => setDecideTarget({ id: r.id, decision: "reject" })}
                        >
                          <X className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  )}
                  {isLeagueLevel && r.status !== "pending" && <TableCell />}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <CreateDialog open={createOpen} onOpenChange={setCreateOpen} />

      {decideTarget && (
        <ConfirmDialog
          open
          onOpenChange={(v) => { if (!v) setDecideTarget(null); }}
          title={decideTarget.decision === "approve" ? "Approve unlock?" : "Reject unlock?"}
          description={
            decideTarget.decision === "approve"
              ? "This will allow the club to edit their season profile even though the season is locked."
              : "The club will be notified that their request was rejected."
          }
          confirmLabel={decideTarget.decision === "approve" ? "Approve" : "Reject"}
          destructive={decideTarget.decision === "reject"}
          loading={decideMutation.isPending}
          onConfirm={() => decideMutation.mutate(decideTarget)}
        />
      )}
    </div>
  );
}
