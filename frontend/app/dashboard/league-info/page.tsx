"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Mail, Pencil, Phone, Trophy } from "lucide-react";

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
  DataTableSkeleton,
  ErrorState,
  PageHeader,
} from "@/components/shared/DataTable";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { leagueInfoApi } from "@/lib/api";
import type { LeagueInfoRead, LeagueInfoUpdate } from "@/types";

// ---------------------------------------------------------------------------
// Edit form
// ---------------------------------------------------------------------------

const editSchema = z.object({
  league_name: z.string().min(1, "Required"),
  founded_year: z
    .string()
    .optional()
    .refine(
      (v) => !v || (/^\d{4}$/.test(v) && Number(v) >= 1800 && Number(v) <= 2100),
      "Must be a valid 4-digit year"
    ),
  president_name: z.string().optional().or(z.literal("")),
  secretary_name: z.string().optional().or(z.literal("")),
  treasurer_name: z.string().optional().or(z.literal("")),
  email: z.string().email("Invalid email").optional().or(z.literal("")),
  phone_number: z.string().optional().or(z.literal("")),
});

type EditForm = z.infer<typeof editSchema>;

function EditLeagueInfoDialog({
  info,
  open,
  onOpenChange,
}: {
  info: LeagueInfoRead;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const queryClient = useQueryClient();

  const form = useForm<EditForm>({
    resolver: zodResolver(editSchema),
    defaultValues: {
      league_name: info.league_name,
      founded_year: info.founded_year ? String(info.founded_year) : "",
      president_name: info.president_name ?? "",
      secretary_name: info.secretary_name ?? "",
      treasurer_name: info.treasurer_name ?? "",
      email: info.email ?? "",
      phone_number: info.phone_number ?? "",
    },
  });

  const mutation = useMutation({
    mutationFn: (data: EditForm) => {
      const payload: LeagueInfoUpdate = {
        league_name: data.league_name,
        founded_year: data.founded_year ? Number(data.founded_year) : null,
        president_name: data.president_name || null,
        secretary_name: data.secretary_name || null,
        treasurer_name: data.treasurer_name || null,
        email: data.email || null,
        phone_number: data.phone_number || null,
      };
      return leagueInfoApi.update(payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["league-info"] });
      toast.success("League info updated");
      onOpenChange(false);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Edit league info</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={form.handleSubmit((d) => mutation.mutate(d))}
          className="space-y-4"
        >
          <div className="space-y-1.5">
            <Label htmlFor="li-name">League name *</Label>
            <Input id="li-name" {...form.register("league_name")} />
            {form.formState.errors.league_name && (
              <p className="text-xs text-destructive">
                {form.formState.errors.league_name.message}
              </p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="li-email">Contact email</Label>
              <Input id="li-email" type="email" {...form.register("email")} />
              {form.formState.errors.email && (
                <p className="text-xs text-destructive">{form.formState.errors.email.message}</p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="li-phone">Phone number</Label>
              <Input id="li-phone" {...form.register("phone_number")} placeholder="+94 11 000 0000" />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="li-year">Founded year</Label>
            <Input id="li-year" {...form.register("founded_year")} placeholder="e.g. 1992" />
            {form.formState.errors.founded_year && (
              <p className="text-xs text-destructive">
                {form.formState.errors.founded_year.message}
              </p>
            )}
          </div>

          <div className="border-t border-border pt-3 space-y-3">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              League Officials
            </p>
            <div className="space-y-1.5">
              <Label htmlFor="li-president">President</Label>
              <Input id="li-president" {...form.register("president_name")} placeholder="Full name" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="li-secretary">Secretary</Label>
              <Input id="li-secretary" {...form.register("secretary_name")} placeholder="Full name" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="li-treasurer">Treasurer</Label>
              <Input id="li-treasurer" {...form.register("treasurer_name")} placeholder="Full name" />
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Saving…" : "Save changes"}
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

export default function LeagueInfoPage() {
  const [editOpen, setEditOpen] = useState(false);
  const { isLeagueLevel } = useCurrentUser();

  const { data: info, isLoading, error, refetch } = useQuery<LeagueInfoRead>({
    queryKey: ["league-info"],
    queryFn: leagueInfoApi.get,
  });

  if (isLoading) return <DataTableSkeleton columns={3} />;
  if (error) return <ErrorState message={(error as Error).message} onRetry={() => refetch()} />;
  if (!info) return null;

  const hasOfficials = info.president_name || info.secretary_name || info.treasurer_name;

  return (
    <div className="space-y-6">
      <PageHeader
        title="League Info"
        description="Official information about the football league"
        action={
          isLeagueLevel ? (
            <Button size="sm" onClick={() => setEditOpen(true)} className="gap-1.5">
              <Pencil className="h-4 w-4" />
              Edit
            </Button>
          ) : undefined
        }
      />

      {/* League identity card */}
      <div className="rounded-xl border border-border bg-card p-6">
        <div className="flex items-start gap-5">
          {/* Logo / trophy icon */}
          <div className="flex items-center justify-center w-16 h-16 rounded-xl bg-primary/10 text-primary shrink-0">
            {info.logo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={info.logo_url}
                alt={info.league_name}
                className="w-full h-full rounded-xl object-cover"
              />
            ) : (
              <Trophy className="h-8 w-8" />
            )}
          </div>

          <div className="flex-1 min-w-0">
            <h1 className="text-xl font-semibold">
              {info.league_name || <span className="text-muted-foreground italic">League name not set</span>}
            </h1>
            {info.founded_year && (
              <p className="text-sm text-muted-foreground mt-0.5">Est. {info.founded_year}</p>
            )}
            <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1">
              {info.email && (
                <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
                  <Mail className="h-3.5 w-3.5" />
                  {info.email}
                </p>
              )}
              {info.phone_number && (
                <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
                  <Phone className="h-3.5 w-3.5" />
                  {info.phone_number}
                </p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Officials */}
      {hasOfficials && (
        <div>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">
            League Officials
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {[
              { label: "President", value: info.president_name },
              { label: "Secretary", value: info.secretary_name },
              { label: "Treasurer", value: info.treasurer_name },
            ]
              .filter((o) => o.value)
              .map(({ label, value }) => (
                <div key={label} className="rounded-lg border border-border bg-card p-4">
                  <p className="text-xs text-muted-foreground mb-1">{label}</p>
                  <p className="text-sm font-medium">{value}</p>
                </div>
              ))}
          </div>
        </div>
      )}

      {!hasOfficials && isLeagueLevel && (
        <div className="rounded-lg border border-dashed border-border p-8 text-center">
          <Trophy className="h-6 w-6 text-muted-foreground mx-auto mb-2" />
          <p className="text-sm text-muted-foreground">No league officials set yet</p>
          <Button
            size="sm"
            variant="outline"
            className="mt-3"
            onClick={() => setEditOpen(true)}
          >
            Add league info
          </Button>
        </div>
      )}

      {info && (
        <EditLeagueInfoDialog
          info={info}
          open={editOpen}
          onOpenChange={setEditOpen}
        />
      )}
    </div>
  );
}
