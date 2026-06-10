"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, Filter, Shield } from "lucide-react";

import { Button } from "@/components/ui/button";
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
import { DataTableSkeleton, EmptyState, ErrorState, PageHeader } from "@/components/shared/DataTable";
import { auditLogsApi } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";
import type { AuditLogRead } from "@/types";

// ---------------------------------------------------------------------------
// Filters
// ---------------------------------------------------------------------------

interface Filters {
  action: string;
  entity_type: string;
  actor_id: string;
  limit: number;
}

const DEFAULT_FILTERS: Filters = { action: "", entity_type: "", actor_id: "", limit: 100 };

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function AuditLogsPage() {
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [applied, setApplied] = useState<Filters>(DEFAULT_FILTERS);

  const { data: logs, isLoading, error, refetch } = useQuery<AuditLogRead[]>({
    queryKey: ["audit-logs", applied],
    queryFn: () =>
      auditLogsApi.list({
        action: applied.action || undefined,
        entity_type: applied.entity_type || undefined,
        actor_id: applied.actor_id ? Number(applied.actor_id) : undefined,
        limit: applied.limit,
      }),
  });

  const exportUrl = auditLogsApi.exportCsv();

  const applyFilters = () => setApplied({ ...filters });
  const resetFilters = () => {
    setFilters(DEFAULT_FILTERS);
    setApplied(DEFAULT_FILTERS);
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title="Audit logs"
        description="Immutable record of all state-changing actions"
        action={
          <a href={exportUrl} download="audit-logs.csv">
            <Button variant="outline" size="sm" className="gap-1.5">
              <Download className="h-4 w-4" />
              Export CSV
            </Button>
          </a>
        }
      />

      {/* Filter bar */}
      <div className="p-4 rounded-lg border border-border bg-card space-y-4">
        <div className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
          <Filter className="h-3.5 w-3.5" />
          Filters
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="space-y-1">
            <Label className="text-xs">Action</Label>
            <Input
              placeholder="e.g. season.create"
              value={filters.action}
              onChange={(e) => setFilters((f) => ({ ...f, action: e.target.value }))}
              className="h-8 text-sm"
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Entity type</Label>
            <Input
              placeholder="e.g. season"
              value={filters.entity_type}
              onChange={(e) => setFilters((f) => ({ ...f, entity_type: e.target.value }))}
              className="h-8 text-sm"
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Actor ID</Label>
            <Input
              type="number"
              placeholder="User ID"
              value={filters.actor_id}
              onChange={(e) => setFilters((f) => ({ ...f, actor_id: e.target.value }))}
              className="h-8 text-sm"
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Limit</Label>
            <Input
              type="number"
              value={filters.limit}
              onChange={(e) =>
                setFilters((f) => ({ ...f, limit: Math.max(1, Number(e.target.value)) }))
              }
              className="h-8 text-sm"
            />
          </div>
        </div>
        <div className="flex gap-2">
          <Button size="sm" onClick={applyFilters}>
            Apply
          </Button>
          <Button size="sm" variant="outline" onClick={resetFilters}>
            Reset
          </Button>
        </div>
      </div>

      {/* Table */}
      {isLoading ? (
        <DataTableSkeleton columns={6} rows={10} />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : !logs?.length ? (
        <EmptyState
          title="No audit log entries"
          description="Actions that change system state will be recorded here"
          icon={<Shield className="h-6 w-6" />}
        />
      ) : (
        <div className="rounded-lg border border-border overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Timestamp</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Entity</TableHead>
                <TableHead>Entity ID</TableHead>
                <TableHead>Actor</TableHead>
                <TableHead>Details</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {logs.map((log) => (
                <TableRow key={log.id} className="hover:bg-muted/50 font-mono text-xs">
                  <TableCell className="text-muted-foreground whitespace-nowrap">
                    {formatDateTime(log.created_at)}
                  </TableCell>
                  <TableCell>
                    <span className="bg-muted px-1.5 py-0.5 rounded text-foreground font-medium">
                      {log.action}
                    </span>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{log.entity_type}</TableCell>
                  <TableCell className="text-muted-foreground">{log.entity_id ?? "—"}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {log.actor_id ? `#${log.actor_id}` : "system"}
                  </TableCell>
                  <TableCell className="max-w-xs">
                    {log.details ? (
                      <span className="truncate block text-muted-foreground">{log.details}</span>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <div className="px-4 py-2 border-t border-border text-xs text-muted-foreground">
            Showing {logs.length} entries
          </div>
        </div>
      )}
    </div>
  );
}
