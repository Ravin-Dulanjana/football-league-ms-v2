"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Plus, Shirt } from "lucide-react";

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
  DataTableSkeleton,
  EmptyState,
  ErrorState,
  PageHeader,
} from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { playersApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { PlayerRead } from "@/types";

const schema = z.object({
  full_name: z.string().min(1, "Full name is required"),
  date_of_birth: z.string().min(1, "Date of birth is required"),
  nic_number: z.string().min(1, "NIC number is required"),
});

type FormData = z.infer<typeof schema>;

export default function PlayersPage() {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();
  const { isLeagueLevel } = useCurrentUser();

  const { data: players, isLoading, error, refetch } = useQuery<PlayerRead[]>({
    queryKey: ["players"],
    queryFn: playersApi.list,
  });

  const form = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { full_name: "", date_of_birth: "", nic_number: "" },
  });

  const createMutation = useMutation({
    mutationFn: (data: FormData) => playersApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["players"] });
      toast.success("Player created");
      setOpen(false);
      form.reset();
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const onSubmit = form.handleSubmit((data) => createMutation.mutate(data));

  return (
    <div>
      <PageHeader
        title="Players"
        description="All registered players in the league"
        action={
          isLeagueLevel ? (
            <Button size="sm" onClick={() => setOpen(true)} className="gap-1.5">
              <Plus className="h-4 w-4" />
              New player
            </Button>
          ) : undefined
        }
      />

      {isLoading ? (
        <DataTableSkeleton columns={5} />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : !players?.length ? (
        <EmptyState
          title="No players yet"
          description="Add the first player to get started"
          icon={<Shirt className="h-6 w-6" />}
          action={
            isLeagueLevel
              ? { label: "Add player", onClick: () => setOpen(true) }
              : undefined
          }
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

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New player</DialogTitle>
          </DialogHeader>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="full_name">Full name *</Label>
              <Input
                id="full_name"
                {...form.register("full_name")}
                placeholder="e.g. Kamal Perera"
              />
              {form.formState.errors.full_name && (
                <p className="text-xs text-destructive">
                  {form.formState.errors.full_name.message}
                </p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="date_of_birth">Date of birth *</Label>
              <Input
                id="date_of_birth"
                type="date"
                {...form.register("date_of_birth")}
              />
              {form.formState.errors.date_of_birth && (
                <p className="text-xs text-destructive">
                  {form.formState.errors.date_of_birth.message}
                </p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="nic_number">NIC number *</Label>
              <Input
                id="nic_number"
                {...form.register("nic_number")}
                placeholder="e.g. 901234567V"
              />
              {form.formState.errors.nic_number && (
                <p className="text-xs text-destructive">
                  {form.formState.errors.nic_number.message}
                </p>
              )}
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Creating…" : "Create player"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
