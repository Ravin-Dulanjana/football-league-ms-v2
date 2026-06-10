"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Building2, ChevronRight, Plus } from "lucide-react";

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
import { useRouter } from "next/navigation";
import { clubsApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { ClubRead } from "@/types";

const schema = z.object({
  name: z.string().min(1, "Name is required"),
  short_name: z.string().optional(),
  code: z.string().min(2, "At least 2 characters").max(10, "At most 10 characters"),
  email: z.string().email("Invalid email address").optional().or(z.literal("")),
});

type FormData = z.infer<typeof schema>;

export default function ClubsPage() {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();
  const { isLeagueLevel } = useCurrentUser();
  const router = useRouter();

  const { data: clubs, isLoading, error, refetch } = useQuery<ClubRead[]>({
    queryKey: ["clubs"],
    queryFn: clubsApi.list,
  });

  const form = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", short_name: "", code: "", email: "" },
  });

  const createMutation = useMutation({
    mutationFn: (data: FormData) =>
      clubsApi.create({
        name: data.name,
        short_name: data.short_name || undefined,
        code: data.code.toUpperCase(),
        email: data.email || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clubs"] });
      toast.success("Club created");
      setOpen(false);
      form.reset();
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const onSubmit = form.handleSubmit((data) => createMutation.mutate(data));

  return (
    <div>
      <PageHeader
        title="Clubs"
        description="All clubs registered in the league"
        action={
          isLeagueLevel ? (
            <Button size="sm" onClick={() => setOpen(true)} className="gap-1.5">
              <Plus className="h-4 w-4" />
              New club
            </Button>
          ) : undefined
        }
      />

      {isLoading ? (
        <DataTableSkeleton columns={5} />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : !clubs?.length ? (
        <EmptyState
          title="No clubs yet"
          description="Add the first club to get started"
          icon={<Building2 className="h-6 w-6" />}
          action={
            isLeagueLevel
              ? { label: "Add club", onClick: () => setOpen(true) }
              : undefined
          }
        />
      ) : (
        <div className="rounded-lg border border-border overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Code</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="w-6" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {clubs.map((club) => (
                <TableRow
                  key={club.id}
                  className="hover:bg-muted/50 cursor-pointer"
                  onClick={() => router.push(`/dashboard/clubs/${club.id}`)}
                >
                  <TableCell>
                    <div>
                      <p className="font-medium">{club.name}</p>
                      {club.short_name && (
                        <p className="text-xs text-muted-foreground">{club.short_name}</p>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="font-mono text-xs">{club.code}</TableCell>
                  <TableCell>
                    <StatusBadge status={club.status} />
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {club.email ?? "—"}
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {formatDate(club.created_at)}
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

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New club</DialogTitle>
          </DialogHeader>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="name">Club name *</Label>
              <Input id="name" {...form.register("name")} placeholder="e.g. Colombo FC" />
              {form.formState.errors.name && (
                <p className="text-xs text-destructive">{form.formState.errors.name.message}</p>
              )}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="short_name">Short name</Label>
                <Input
                  id="short_name"
                  {...form.register("short_name")}
                  placeholder="e.g. CFC"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="code">Code *</Label>
                <Input
                  id="code"
                  {...form.register("code")}
                  placeholder="e.g. COL"
                  className="uppercase"
                  style={{ textTransform: "uppercase" }}
                />
                {form.formState.errors.code && (
                  <p className="text-xs text-destructive">{form.formState.errors.code.message}</p>
                )}
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="email">Contact email</Label>
              <Input
                id="email"
                type="email"
                {...form.register("email")}
                placeholder="admin@club.lk"
              />
              {form.formState.errors.email && (
                <p className="text-xs text-destructive">{form.formState.errors.email.message}</p>
              )}
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Creating…" : "Create club"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
