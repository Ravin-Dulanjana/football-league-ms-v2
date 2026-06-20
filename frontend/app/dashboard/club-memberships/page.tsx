"use client";

import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { UserPlus } from "lucide-react";

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
  DataTableSkeleton,
  EmptyState,
  ErrorState,
  PageHeader,
} from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { clubMembershipsApi, clubsApi } from "@/lib/api";
import { formatRelative } from "@/lib/utils";
import type { ClubMembershipRequestRead, ClubRead } from "@/types";

export default function ClubMembershipsPage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data: clubs } = useQuery<ClubRead[]>({
    queryKey: ["clubs"],
    queryFn: clubsApi.list,
  });
  const clubMap = Object.fromEntries((clubs ?? []).map((c) => [c.id, c.name]));

  const { data: requests = [], isLoading, error, refetch } =
    useQuery<ClubMembershipRequestRead[]>({
      queryKey: ["club-memberships", "requests"],
      queryFn: clubMembershipsApi.listRequests,
    });

  const decideMutation = useMutation({
    mutationFn: ({ id, decision }: { id: number; decision: "accept" | "reject" }) =>
      clubMembershipsApi.decide(id, { decision }),
    onSuccess: (_, { decision }) => {
      queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
      queryClient.invalidateQueries({ queryKey: ["club-memberships"] });
      queryClient.invalidateQueries({ queryKey: ["players"] });
      if (decision === "accept") {
        toast.success("You've joined the club!");
        router.push("/dashboard");
      } else {
        toast.success("Invite declined");
      }
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const pending = requests.filter((r) => r.status === "pending");
  const past = requests.filter((r) => r.status !== "pending");

  return (
    <div>
      <PageHeader
        title="Club Invites"
        description="Clubs that have invited you to join"
      />

      {isLoading ? (
        <DataTableSkeleton columns={3} />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : requests.length === 0 ? (
        <EmptyState
          title="No invites yet"
          description="Club admins can invite you to join their club"
          icon={<UserPlus className="h-6 w-6" />}
        />
      ) : (
        <div className="space-y-6">
          {pending.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                Pending ({pending.length})
              </p>
              <div className="rounded-lg border border-border overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Club</TableHead>
                      <TableHead>Sent</TableHead>
                      <TableHead />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {pending.map((req) => (
                      <TableRow key={req.id}>
                        <TableCell className="font-medium text-sm">
                          {clubMap[req.club_id] ?? `Club #${req.club_id}`}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {formatRelative(req.created_at)}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1">
                            <Button
                              size="sm"
                              variant="default"
                              className="h-7 text-xs"
                              onClick={() =>
                                decideMutation.mutate({ id: req.id, decision: "accept" })
                              }
                              disabled={decideMutation.isPending}
                            >
                              Accept
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-7 text-xs text-muted-foreground hover:text-destructive"
                              onClick={() =>
                                decideMutation.mutate({ id: req.id, decision: "reject" })
                              }
                              disabled={decideMutation.isPending}
                            >
                              Decline
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          )}

          {past.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                History
              </p>
              <div className="rounded-lg border border-border overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Club</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Responded</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {past.map((req) => (
                      <TableRow key={req.id}>
                        <TableCell className="font-medium text-sm">
                          {clubMap[req.club_id] ?? `Club #${req.club_id}`}
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={req.status} />
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {req.responded_at ? formatRelative(req.responded_at) : "—"}
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
    </div>
  );
}
