"use client";

import { useQuery } from "@tanstack/react-query";
import { Shirt } from "lucide-react";

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
import type { PlayerRead } from "@/types";

export default function PlayersPage() {
  const { data: players, isLoading, error, refetch } = useQuery<PlayerRead[]>({
    queryKey: ["players"],
    queryFn: playersApi.list,
  });

  return (
    <div>
      <PageHeader
        title="Players"
        description="All registered players in the league. Create player accounts from the Users page."
      />

      {isLoading ? (
        <DataTableSkeleton columns={5} />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : !players?.length ? (
        <EmptyState
          title="No players yet"
          description="Create a player account from the Users page to get started"
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
              </TableRow>
            </TableHeader>
            <TableBody>
              {players.map((player) => (
                <TableRow key={player.id} className="hover:bg-muted/50">
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
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
