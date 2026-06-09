"use client";

import { useQuery } from "@tanstack/react-query";
import { BarChart3, Building2, ClipboardList, FileText, Shirt } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { DataTableSkeleton, EmptyState, ErrorState, PageHeader } from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { reportsApi } from "@/lib/api";
import type { AnalyticsSummary } from "@/types";

// ---------------------------------------------------------------------------
// Stat card
// ---------------------------------------------------------------------------

function StatCard({
  title,
  value,
  icon: Icon,
  loading,
}: {
  title: string;
  value: number | undefined;
  icon: React.ElementType;
  loading: boolean;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-8 w-16" />
        ) : (
          <p className="text-3xl font-bold tabular-nums">{value ?? "—"}</p>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function AnalyticsPage() {
  const { data, isLoading, error, refetch } = useQuery<AnalyticsSummary>({
    queryKey: ["analytics"],
    queryFn: reportsApi.analytics,
    staleTime: 60 * 1000,
  });

  return (
    <div className="space-y-8">
      <PageHeader
        title="Analytics"
        description="League-wide statistics and club breakdown"
      />

      {/* Summary stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total clubs"
          value={data?.total_clubs}
          icon={Building2}
          loading={isLoading}
        />
        <StatCard
          title="Active players"
          value={data?.active_players}
          icon={Shirt}
          loading={isLoading}
        />
        <StatCard
          title="Pending registrations"
          value={data?.pending_registration_requests}
          icon={ClipboardList}
          loading={isLoading}
        />
        <StatCard
          title="Pending releases"
          value={data?.pending_releases}
          icon={FileText}
          loading={isLoading}
        />
      </div>

      {/* By-club breakdown */}
      <div>
        <h2 className="text-base font-semibold mb-4">Club breakdown</h2>

        {isLoading ? (
          <DataTableSkeleton columns={5} />
        ) : error ? (
          <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
        ) : !data?.by_club?.length ? (
          <EmptyState
            title="No club data"
            description="Club-level analytics will appear here once clubs and registrations are created"
            icon={<BarChart3 className="h-6 w-6" />}
          />
        ) : (
          <div className="rounded-lg border border-border overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Club</TableHead>
                  <TableHead>Profile status</TableHead>
                  <TableHead className="text-right">Active players</TableHead>
                  <TableHead className="text-right">Pending registrations</TableHead>
                  <TableHead className="text-right">Pending releases</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.by_club.map((club) => (
                  <TableRow key={club.club_id} className="hover:bg-muted/50">
                    <TableCell className="font-medium">{club.club_name}</TableCell>
                    <TableCell>
                      {club.profile_status ? (
                        <StatusBadge status={club.profile_status} />
                      ) : (
                        <span className="text-muted-foreground text-sm">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{club.active_players}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {club.pending_registrations > 0 ? (
                        <span className="text-amber-600 font-medium">
                          {club.pending_registrations}
                        </span>
                      ) : (
                        club.pending_registrations
                      )}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {club.pending_releases > 0 ? (
                        <span className="text-amber-600 font-medium">{club.pending_releases}</span>
                      ) : (
                        club.pending_releases
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </div>
  );
}
