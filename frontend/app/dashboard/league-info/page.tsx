"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm, Controller } from "react-hook-form";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DataTableSkeleton,
  ErrorState,
  PageHeader,
} from "@/components/shared/DataTable";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { leagueInfoApi, playersApi } from "@/lib/api";
import type { LeagueInfoRead, LeagueInfoUpdate, PlayerRead } from "@/types";

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
  president_player_id: z.number().optional().nullable(),
  secretary_player_id: z.number().optional().nullable(),
  treasurer_player_id: z.number().optional().nullable(),
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

  const { data: allPlayers = [] } = useQuery<PlayerRead[]>({
    queryKey: ["players"],
    queryFn: playersApi.list,
    enabled: open,
  });

  const form = useForm<EditForm>({
    resolver: zodResolver(editSchema),
    defaultValues: {
      league_name: info.league_name,
      founded_year: info.founded_year ? String(info.founded_year) : "",
      president_player_id: info.president_player_id ?? null,
      secretary_player_id: info.secretary_player_id ?? null,
      treasurer_player_id: info.treasurer_player_id ?? null,
      email: info.email ?? "",
      phone_number: info.phone_number ?? "",
    },
  });

  const mutation = useMutation({
    mutationFn: (data: EditForm) => {
      const payload: LeagueInfoUpdate = {
        league_name: data.league_name,
        founded_year: data.founded_year ? Number(data.founded_year) : null,
        president_player_id: data.president_player_id ?? null,
        secretary_player_id: data.secretary_player_id ?? null,
        treasurer_player_id: data.treasurer_player_id ?? null,
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
            <p className="text-xs text-muted-foreground -mt-1">
              Link to an existing member profile
            </p>
            {(["president", "secretary", "treasurer"] as const).map((role) => {
              const fieldKey = `${role}_player_id` as keyof EditForm;
              return (
                <div key={role} className="space-y-1.5">
                  <Label className="capitalize">{role}</Label>
                  <Controller
                    control={form.control}
                    name={fieldKey}
                    render={({ field }) => (
                      <Select
                        value={field.value ? String(field.value) : "none"}
                        onValueChange={(v) =>
                          field.onChange(v === "none" ? null : Number(v))
                        }
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Not assigned" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">Not assigned</SelectItem>
                          {allPlayers.map((p) => (
                            <SelectItem key={p.id} value={String(p.id)}>
                              {p.full_name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  />
                </div>
              );
            })}
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
  const router = useRouter();
  const { isLeagueLevel } = useCurrentUser();

  const { data: info, isLoading, error, refetch } = useQuery<LeagueInfoRead>({
    queryKey: ["league-info"],
    queryFn: leagueInfoApi.get,
  });

  if (isLoading) return <DataTableSkeleton columns={3} />;
  if (error) return <ErrorState message={(error as Error).message} onRetry={() => refetch()} />;
  if (!info) return null;

  const hasOfficials = info.president || info.secretary || info.treasurer;

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
            {([
              { label: "President", official: info.president },
              { label: "Secretary", official: info.secretary },
              { label: "Treasurer", official: info.treasurer },
            ] as { label: string; official: typeof info.president }[])
              .filter((o) => o.official)
              .map(({ label, official }) => (
                <button
                  key={label}
                  onClick={() => router.push(`/dashboard/players/${official!.id}`)}
                  className="flex items-center gap-3 p-3 rounded-lg border border-border bg-card hover:bg-muted/50 transition-colors text-left"
                >
                  <div className="w-10 h-10 rounded-full bg-primary/10 text-primary text-sm font-bold flex items-center justify-center shrink-0 overflow-hidden">
                    {official!.photo_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={official!.photo_url}
                        alt={official!.full_name}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      official!.full_name.charAt(0).toUpperCase()
                    )}
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs text-muted-foreground">{label}</p>
                    <p className="text-sm font-medium truncate">{official!.full_name}</p>
                  </div>
                </button>
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
