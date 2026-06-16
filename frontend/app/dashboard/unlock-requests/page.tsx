"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Check, Clock, Key, X } from "lucide-react";

import { Button } from "@/components/ui/button";
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
import { unlockRequestsApi, clubsApi } from "@/lib/api";
import { formatRelative } from "@/lib/utils";
import type { ClubRead, UnlockRequestRead } from "@/types";

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function UnlockRequestsPage() {
  const [decideTarget, setDecideTarget] = useState<{
    id: number;
    decision: "approve" | "reject";
  } | null>(null);
  const queryClient = useQueryClient();
  const { user, isLeagueLevel } = useCurrentUser();
  const myClubId = user?.club_id ?? null;

  const { data: requests, isLoading, error, refetch } = useQuery<UnlockRequestRead[]>({
    queryKey: ["unlock-requests"],
    queryFn: unlockRequestsApi.list,
  });

  const { data: clubs = [] } = useQuery<ClubRead[]>({
    queryKey: ["clubs"],
    queryFn: clubsApi.list,
  });
  const clubMap = new Map(clubs.map((c) => [c.id, c]));

  const decideMutation = useMutation({
    mutationFn: ({ id, decision }: { id: number; decision: "approve" | "reject" }) =>
      unlockRequestsApi.decide(id, decision),
    onSuccess: (_, { decision }) => {
      queryClient.invalidateQueries({ queryKey: ["unlock-requests"] });
      queryClient.invalidateQueries({ queryKey: ["profiles"] });
      toast.success(decision === "approve" ? "Approval recorded" : "Request rejected");
      setDecideTarget(null);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <div>
      <PageHeader
        title="Late Submission Approvals"
        description="Squad submissions made after the registration window closed — 2 league admins from different clubs must approve"
      />

      {isLoading ? (
        <DataTableSkeleton columns={6} />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : !requests?.length ? (
        <EmptyState
          title="No late submissions"
          description="When a club submits their squad after the registration window closes, it will appear here for approval."
          icon={<Key className="h-6 w-6" />}
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
              {requests.map((r) => {
                const submittingClub = clubMap.get(r.club_id);
                const approverClubNames = r.approver_club_ids
                  .map((id) => clubMap.get(id)?.name ?? `Club ${id}`)
                  .join(", ");
                const myClubAlreadyApproved =
                  myClubId !== null && r.approver_club_ids.includes(myClubId);
                const canApprove =
                  isLeagueLevel &&
                  r.status === "pending" &&
                  !myClubAlreadyApproved;
                const canReject = isLeagueLevel && r.status === "pending";

                return (
                  <TableRow key={r.id} className="hover:bg-muted/50">
                    <TableCell className="font-medium">
                      {submittingClub?.name ?? `Club ${r.club_id}`}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      Season {r.season_id}
                    </TableCell>
                    <TableCell className="max-w-xs">
                      <p className="text-sm truncate">{r.reason}</p>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col gap-0.5">
                        <span className="text-sm font-medium">
                          {r.approver_club_ids.length}/2 clubs
                        </span>
                        {r.approver_club_ids.length > 0 && (
                          <span className="text-xs text-muted-foreground">
                            {approverClubNames}
                          </span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1.5">
                        <StatusBadge status={r.status} />
                        {r.status === "pending" && (
                          <Clock className="h-3.5 w-3.5 text-amber-500" />
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatRelative(r.created_at)}
                    </TableCell>
                    {isLeagueLevel && (
                      <TableCell>
                        <div className="flex items-center gap-1.5">
                          {canApprove && (
                            <Button
                              variant="outline"
                              size="icon"
                              className="h-7 w-7 border-green-500 text-green-600 hover:bg-green-50 dark:hover:bg-green-950"
                              onClick={() => setDecideTarget({ id: r.id, decision: "approve" })}
                              title="Approve on behalf of your club"
                            >
                              <Check className="h-3.5 w-3.5" />
                            </Button>
                          )}
                          {myClubAlreadyApproved && r.status === "pending" && (
                            <span className="text-xs text-green-600 flex items-center gap-1">
                              <Check className="h-3 w-3" />
                              Your club approved
                            </span>
                          )}
                          {canReject && (
                            <Button
                              variant="outline"
                              size="icon"
                              className="h-7 w-7 border-red-400 text-red-600 hover:bg-red-50 dark:hover:bg-red-950"
                              onClick={() => setDecideTarget({ id: r.id, decision: "reject" })}
                              title="Reject"
                            >
                              <X className="h-3.5 w-3.5" />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    )}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}

      {decideTarget && (
        <ConfirmDialog
          open
          onOpenChange={(v) => { if (!v) setDecideTarget(null); }}
          title={
            decideTarget.decision === "approve"
              ? "Approve late submission?"
              : "Reject late submission?"
          }
          description={
            decideTarget.decision === "approve"
              ? "You are approving this club's late squad submission on behalf of your club. A second approval from a different club is required before the submission is accepted."
              : "The late submission will be rejected. The club will need to resubmit to restart the approval process."
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
