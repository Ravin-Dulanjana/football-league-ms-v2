"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Check, FileText, Plus, X } from "lucide-react";

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
import { releasesApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { ReleaseRead } from "@/types";

// ---------------------------------------------------------------------------
// Create dialog
// The release requires an existing registration_id and a document.
// For now the form captures the registration_id as a number and a doc URL/key.
// ---------------------------------------------------------------------------

const schema = z.object({
  registration_id: z.number().int().positive("Registration ID is required"),
  s3_key: z.string().min(1, "Document S3 key is required"),
  file_name: z.string().min(1, "File name is required"),
  effective_date: z.string().optional(),
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

  const form = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { registration_id: 0, s3_key: "", file_name: "", effective_date: "" },
  });

  const mutation = useMutation({
    mutationFn: (data: FormData) =>
      releasesApi.create({
        registration_id: data.registration_id,
        s3_key: data.s3_key,
        file_name: data.file_name,
        effective_date: data.effective_date || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["releases"] });
      toast.success("Release created");
      onOpenChange(false);
      form.reset();
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New release request</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={form.handleSubmit((d) => mutation.mutate(d))}
          className="space-y-4"
        >
          <div className="space-y-1.5">
            <Label htmlFor="reg-id">Registration ID *</Label>
            <Input
              id="reg-id"
              type="number"
              {...form.register("registration_id", { valueAsNumber: true })}
              placeholder="Active registration ID"
            />
            {form.formState.errors.registration_id && (
              <p className="text-xs text-destructive">
                {form.formState.errors.registration_id.message}
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="file_name">Document file name *</Label>
            <Input
              id="file_name"
              {...form.register("file_name")}
              placeholder="release-letter.pdf"
            />
            {form.formState.errors.file_name && (
              <p className="text-xs text-destructive">
                {form.formState.errors.file_name.message}
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="s3_key">Document S3 key *</Label>
            <Input
              id="s3_key"
              {...form.register("s3_key")}
              placeholder="documents/releases/..."
            />
            {form.formState.errors.s3_key && (
              <p className="text-xs text-destructive">
                {form.formState.errors.s3_key.message}
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="effective_date">Effective date</Label>
            <Input id="effective_date" type="date" {...form.register("effective_date")} />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Creating…" : "Create release"}
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

export default function ReleasesPage() {
  const [createOpen, setCreateOpen] = useState(false);
  const [decideTarget, setDecideTarget] = useState<{
    id: number;
    decision: "confirm" | "reject";
  } | null>(null);
  const queryClient = useQueryClient();
  const { isAnyAdmin, isPlayer } = useCurrentUser();

  const { data: releases, isLoading, error, refetch } = useQuery<ReleaseRead[]>({
    queryKey: ["releases"],
    queryFn: releasesApi.list,
  });

  const decideMutation = useMutation({
    mutationFn: ({ id, decision }: { id: number; decision: "confirm" | "reject" }) =>
      releasesApi.decide(id, decision),
    onSuccess: (_, { decision }) => {
      queryClient.invalidateQueries({ queryKey: ["releases"] });
      toast.success(decision === "confirm" ? "Release confirmed" : "Release rejected");
      setDecideTarget(null);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const pending = releases?.filter((r) => r.status === "pending_player_confirmation") ?? [];
  const historical = releases?.filter((r) => r.status !== "pending_player_confirmation") ?? [];

  return (
    <div>
      <PageHeader
        title="Releases"
        description="Player release requests"
        action={
          isAnyAdmin ? (
            <Button size="sm" onClick={() => setCreateOpen(true)} className="gap-1.5">
              <Plus className="h-4 w-4" />
              New release
            </Button>
          ) : undefined
        }
      />

      {isLoading ? (
        <DataTableSkeleton columns={6} />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : !releases?.length ? (
        <EmptyState
          title="No release requests"
          description="No releases have been created yet"
          icon={<FileText className="h-6 w-6" />}
          action={
            isAnyAdmin ? { label: "New release", onClick: () => setCreateOpen(true) } : undefined
          }
        />
      ) : (
        <div className="space-y-6">
          {pending.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">
                Awaiting decision ({pending.length})
              </h2>
              <div className="rounded-lg border border-border overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>ID</TableHead>
                      <TableHead>Player</TableHead>
                      <TableHead>From club</TableHead>
                      <TableHead>Effective date</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Created</TableHead>
                      {isPlayer && <TableHead />}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {pending.map((r) => (
                      <TableRow key={r.id} className="hover:bg-muted/50">
                        <TableCell className="text-muted-foreground">#{r.id}</TableCell>
                        <TableCell>Player {r.player_id}</TableCell>
                        <TableCell>Club {r.from_club_id}</TableCell>
                        <TableCell className="text-sm">
                          {r.effective_date ? formatDate(r.effective_date) : "—"}
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={r.status} />
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {formatDate(r.created_at)}
                        </TableCell>
                        {isPlayer && (
                          <TableCell>
                            <div className="flex gap-1">
                              <Button
                                variant="outline"
                                size="icon"
                                className="h-7 w-7 border-green-500 text-green-600 hover:bg-green-50"
                                onClick={() =>
                                  setDecideTarget({ id: r.id, decision: "confirm" })
                                }
                              >
                                <Check className="h-3.5 w-3.5" />
                              </Button>
                              <Button
                                variant="outline"
                                size="icon"
                                className="h-7 w-7 border-red-400 text-red-600 hover:bg-red-50"
                                onClick={() =>
                                  setDecideTarget({ id: r.id, decision: "reject" })
                                }
                              >
                                <X className="h-3.5 w-3.5" />
                              </Button>
                            </div>
                          </TableCell>
                        )}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          )}

          {historical.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">
                History
              </h2>
              <div className="rounded-lg border border-border overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>ID</TableHead>
                      <TableHead>Player</TableHead>
                      <TableHead>From club</TableHead>
                      <TableHead>Effective date</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Created</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {historical.map((r) => (
                      <TableRow key={r.id} className="hover:bg-muted/50">
                        <TableCell className="text-muted-foreground">#{r.id}</TableCell>
                        <TableCell>Player {r.player_id}</TableCell>
                        <TableCell>Club {r.from_club_id}</TableCell>
                        <TableCell className="text-sm">
                          {r.effective_date ? formatDate(r.effective_date) : "—"}
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={r.status} />
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {formatDate(r.created_at)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          )}
        </div>
      )}

      <CreateDialog open={createOpen} onOpenChange={setCreateOpen} />

      {decideTarget && (
        <ConfirmDialog
          open
          onOpenChange={(v) => { if (!v) setDecideTarget(null); }}
          title={decideTarget.decision === "confirm" ? "Confirm release?" : "Reject release?"}
          description={
            decideTarget.decision === "confirm"
              ? "You are confirming your release from the club. This action cannot be undone."
              : "You are rejecting this release request."
          }
          confirmLabel={decideTarget.decision === "confirm" ? "Confirm release" : "Reject"}
          destructive={decideTarget.decision === "confirm"}
          loading={decideMutation.isPending}
          onConfirm={() => decideMutation.mutate(decideTarget)}
        />
      )}
    </div>
  );
}
