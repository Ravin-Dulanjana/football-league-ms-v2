"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { ChevronDown, ChevronUp, ExternalLink, FileText, ListChecks } from "lucide-react";

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
import { profilesApi, clubsApi, seasonsApi, registrationsApi, staffApi, playersApi, releasesApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type {
  ClubRead,
  ClubSeasonProfileRead,
  ClubStaffRead,
  PlayerRead,
  PlayerSeasonRegistrationRead,
  ReleaseRead,
  SeasonRead,
} from "@/types";

// ---------------------------------------------------------------------------
// Transition dialog
// ---------------------------------------------------------------------------

const transitionSchema = z.object({
  comment: z.string().optional(),
});
type TransitionForm = z.infer<typeof transitionSchema>;

function TransitionDialog({
  profile,
  action,
  open,
  onOpenChange,
}: {
  profile: ClubSeasonProfileRead;
  action: "reviewed" | "approved" | "returned";
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const form = useForm<TransitionForm>({
    resolver: zodResolver(transitionSchema),
    defaultValues: { comment: "" },
  });

  const mutation = useMutation({
    mutationFn: (data: TransitionForm) =>
      profilesApi.transition(profile.id, {
        target_status: action,
        comment: data.comment || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profiles"] });
      toast.success(`Submission ${action}`);
      onOpenChange(false);
      form.reset();
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const labels: Record<string, string> = {
    reviewed: "Mark as Reviewed",
    approved: "Approve",
    returned: "Return to Club",
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{labels[action]}</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={form.handleSubmit((d) => mutation.mutate(d))}
          className="space-y-4"
        >
          <div className="space-y-1.5">
            <Label htmlFor="transition-comment">Comment (optional)</Label>
            <Textarea
              id="transition-comment"
              rows={3}
              {...form.register("comment")}
              placeholder="Add a note for the club admin…"
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={mutation.isPending}
              variant={action === "returned" ? "destructive" : "default"}
            >
              {mutation.isPending ? "Saving…" : labels[action]}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Submission row (expandable)
// ---------------------------------------------------------------------------

function SubmissionRow({
  profile,
  clubMap,
  seasonMap,
}: {
  profile: ClubSeasonProfileRead;
  clubMap: Map<number, ClubRead>;
  seasonMap: Map<number, SeasonRead>;
}) {
  const router = useRouter();
  const [expanded, setExpanded] = useState(false);
  const [transitionAction, setTransitionAction] = useState<
    "reviewed" | "approved" | "returned" | null
  >(null);

  const { data: squadRegs = [] } = useQuery<PlayerSeasonRegistrationRead[]>({
    queryKey: ["player-season-registrations", profile.club_id, profile.season_id],
    queryFn: () =>
      registrationsApi.listPlayerSeasonRegistrations({
        club_id: profile.club_id,
        season_id: profile.season_id,
      }),
    enabled: expanded,
  });

  const { data: squadStaff = [] } = useQuery<ClubStaffRead[]>({
    queryKey: ["club-staff", profile.club_id, profile.season_id],
    queryFn: () => staffApi.list(profile.club_id, profile.season_id),
    enabled: expanded,
  });

  const { data: allPlayers = [] } = useQuery<PlayerRead[]>({
    queryKey: ["players"],
    queryFn: playersApi.list,
    enabled: expanded,
  });
  const playerMap = new Map(allPlayers.map((p) => [p.id, p]));

  const { data: allReleases = [] } = useQuery<ReleaseRead[]>({
    queryKey: ["releases"],
    queryFn: releasesApi.list,
    enabled: expanded,
  });

  const club = clubMap.get(profile.club_id);
  const season = seasonMap.get(profile.season_id);
  const canReview = profile.status === "submitted" || profile.status === "resubmitted";
  const canApprove = profile.status === "reviewed";
  const canReturn =
    profile.status === "submitted" ||
    profile.status === "resubmitted" ||
    profile.status === "reviewed";

  return (
    <>
      <TableRow className="hover:bg-muted/50">
        <TableCell>
          <button
            className="font-medium text-sm hover:text-primary transition-colors text-left"
            onClick={() => router.push(`/dashboard/clubs/${profile.club_id}`)}
          >
            {club?.name ?? `Club ${profile.club_id}`}
          </button>
        </TableCell>
        <TableCell className="text-sm">{season?.name ?? `Season ${profile.season_id}`}</TableCell>
        <TableCell>
          <StatusBadge status={profile.status} />
        </TableCell>
        <TableCell className="text-sm text-muted-foreground">
          {profile.submitted_at ? formatDate(profile.submitted_at) : "—"}
        </TableCell>
        <TableCell>
          <div className="flex items-center gap-1.5">
            {canReview && (
              <Button
                size="sm"
                variant="outline"
                className="h-7 text-xs"
                onClick={() => setTransitionAction("reviewed")}
              >
                Review
              </Button>
            )}
            {canApprove && (
              <Button
                size="sm"
                className="h-7 text-xs"
                onClick={() => setTransitionAction("approved")}
              >
                Approve
              </Button>
            )}
            {canReturn && (
              <Button
                size="sm"
                variant="outline"
                className="h-7 text-xs text-destructive border-destructive/40 hover:bg-destructive/5"
                onClick={() => setTransitionAction("returned")}
              >
                Return
              </Button>
            )}
            <Button
              size="icon"
              variant="ghost"
              className="h-7 w-7"
              onClick={() => setExpanded((v) => !v)}
            >
              {expanded ? (
                <ChevronUp className="h-3.5 w-3.5" />
              ) : (
                <ChevronDown className="h-3.5 w-3.5" />
              )}
            </Button>
          </div>
        </TableCell>
      </TableRow>

      {expanded && (
        <TableRow>
          <TableCell colSpan={5} className="bg-muted/30 p-4">
            <div className="space-y-4">
              {/* Players */}
              <div>
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                  Players ({squadRegs.length}/30)
                </p>
                {squadRegs.length === 0 ? (
                  <p className="text-xs text-muted-foreground">No players registered.</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {squadRegs.map((reg) => {
                      const player = playerMap.get(reg.player_id);
                      const released = allReleases.some(
                        (r) => r.registration_id === reg.id && r.status === "confirmed"
                      );
                      return (
                        <button
                          key={reg.id}
                          onClick={() =>
                            router.push(`/dashboard/players/${reg.player_id}`)
                          }
                          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-medium transition-colors ${
                            released
                              ? "border-muted text-muted-foreground bg-muted/50 line-through"
                              : "border-border bg-card hover:bg-muted/50"
                          }`}
                        >
                          {player?.full_name ?? `Player ${reg.player_id}`}
                          {released && (
                            <span className="text-[10px] text-muted-foreground">(released)</span>
                          )}
                          <ExternalLink className="h-2.5 w-2.5 text-muted-foreground" />
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Staff */}
              <div>
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                  Support Staff ({squadStaff.length}/6)
                </p>
                {squadStaff.length === 0 ? (
                  <p className="text-xs text-muted-foreground">No staff added.</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {squadStaff.map((s) => (
                      <span
                        key={s.id}
                        className="px-2.5 py-1 rounded-full border border-border bg-card text-xs"
                      >
                        {s.full_name}
                        <span className="text-muted-foreground ml-1">({s.role})</span>
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Release docs */}
              {allReleases.filter((r) => r.from_club_id === profile.club_id && r.status === "confirmed").length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                    Confirmed Releases
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {allReleases
                      .filter((r) => r.from_club_id === profile.club_id && r.status === "confirmed")
                      .map((r) => {
                        const player = playerMap.get(r.player_id);
                        return r.documents.map((doc) => (
                          <a
                            key={doc.id}
                            href={doc.file_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-1 text-xs text-primary hover:underline"
                          >
                            <FileText className="h-3 w-3" />
                            {player?.full_name ?? `Player ${r.player_id}`} — {doc.file_name}
                          </a>
                        ));
                      })}
                  </div>
                </div>
              )}
            </div>
          </TableCell>
        </TableRow>
      )}

      {transitionAction && (
        <TransitionDialog
          profile={profile}
          action={transitionAction}
          open
          onOpenChange={(v) => { if (!v) setTransitionAction(null); }}
        />
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function SubmissionsPage() {
  const { data: profiles = [], isLoading, error, refetch } = useQuery<ClubSeasonProfileRead[]>({
    queryKey: ["profiles"],
    queryFn: profilesApi.list,
  });

  const { data: clubs = [] } = useQuery<ClubRead[]>({
    queryKey: ["clubs"],
    queryFn: clubsApi.list,
  });

  const { data: seasons = [] } = useQuery<SeasonRead[]>({
    queryKey: ["seasons"],
    queryFn: seasonsApi.list,
  });

  const clubMap = new Map(clubs.map((c) => [c.id, c]));
  const seasonMap = new Map(seasons.map((s) => [s.id, s]));

  // Show submitted + active states first; filter out pure drafts
  const relevant = profiles
    .filter((p) => p.status !== "draft")
    .sort(
      (a, b) =>
        new Date(b.submitted_at ?? b.created_at).getTime() -
        new Date(a.submitted_at ?? a.created_at).getTime()
    );

  return (
    <div>
      <PageHeader
        title="Squad Submissions"
        description="Club squad lists submitted for the current season"
      />

      {isLoading ? (
        <DataTableSkeleton columns={5} />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : relevant.length === 0 ? (
        <EmptyState
          title="No submissions yet"
          description="Squad lists submitted by clubs will appear here"
          icon={<ListChecks className="h-6 w-6" />}
        />
      ) : (
        <div className="rounded-lg border border-border overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Club</TableHead>
                <TableHead>Season</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Submitted</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {relevant.map((profile) => (
                <SubmissionRow
                  key={profile.id}
                  profile={profile}
                  clubMap={clubMap}
                  seasonMap={seasonMap}
                />
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
