"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight, Search, Shirt, X } from "lucide-react";
import { useRouter } from "next/navigation";

import { Input } from "@/components/ui/input";
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
import { playersApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { PlayerRead, PlayerStatus } from "@/types";

const STATUS_OPTIONS: { label: string; value: PlayerStatus | "all" }[] = [
  { label: "All statuses", value: "all" },
  { label: "Active", value: "active" },
  { label: "Pending claim", value: "pending_claim" },
  { label: "Inactive", value: "inactive" },
];

export default function PlayersPage() {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<PlayerStatus | "all">("all");

  const { data: players, isLoading, error, refetch } = useQuery<PlayerRead[]>({
    queryKey: ["players"],
    queryFn: playersApi.list,
  });

  const filtered = players?.filter((p) => {
    const matchesSearch =
      !search ||
      p.full_name.toLowerCase().includes(search.toLowerCase()) ||
      p.league_player_code.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = statusFilter === "all" || p.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const hasFilters = search || statusFilter !== "all";

  return (
    <div>
      <PageHeader
        title="Players"
        description="All registered players in the league. Create player accounts from the Users page."
      />

      {/* Filters */}
      <div className="flex items-center gap-2 mb-4">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
          <Input
            placeholder="Search name or code…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8 h-8 text-sm"
          />
          {search && (
            <button
              onClick={() => setSearch("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        <Select
          value={statusFilter}
          onValueChange={(v) => setStatusFilter(v as PlayerStatus | "all")}
        >
          <SelectTrigger className="w-44 h-8 text-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map((o) => (
              <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        {hasFilters && (
          <button
            onClick={() => { setSearch(""); setStatusFilter("all"); }}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          >
            <X className="h-3 w-3" /> Clear
          </button>
        )}

        {filtered && players && filtered.length !== players.length && (
          <span className="text-xs text-muted-foreground ml-1">
            {filtered.length} of {players.length}
          </span>
        )}
      </div>

      {isLoading ? (
        <DataTableSkeleton columns={5} />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : !filtered?.length ? (
        <EmptyState
          title={hasFilters ? "No players match the filter" : "No players yet"}
          description={hasFilters ? "Try adjusting the search or status filter" : "Create a player account from the Users page to get started"}
          icon={<Shirt className="h-6 w-6" />}
        />
      ) : (
        <div className="rounded-lg border border-border overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Code</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Date of birth</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="w-6" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((player) => (
                <TableRow
                  key={player.id}
                  className="hover:bg-muted/50 cursor-pointer"
                  onClick={() => router.push(`/dashboard/players/${player.id}`)}
                >
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {player.league_player_code}
                  </TableCell>
                  <TableCell className="font-medium">{player.full_name}</TableCell>
                  <TableCell className="text-sm">{formatDate(player.date_of_birth)}</TableCell>
                  <TableCell>
                    <StatusBadge status={player.status} />
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatDate(player.created_at)}
                  </TableCell>
                  <TableCell className="w-6">
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
