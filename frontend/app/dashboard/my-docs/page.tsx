"use client";

import { useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import {
  BookOpen,
  Building2,
  CalendarDays,
  EyeOff,
  Eye,
  ExternalLink,
  FilePlus,
  Lock,
  Plus,
  Trophy,
  Upload,
} from "lucide-react";

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
import { PageHeader } from "@/components/shared/DataTable";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { playersApi } from "@/lib/api";
import { cn, formatDate } from "@/lib/utils";
import type { PlayerDocumentRead } from "@/types";

// ---------------------------------------------------------------------------
// Add release doc dialog — manual entry
// ---------------------------------------------------------------------------

const addSchema = z.object({
  year: z.string().min(4, "Required"),
  league_name: z.string().min(1, "League name is required"),
  club_name: z.string().min(1, "Club name is required"),
  description: z.string().optional(),
});
type AddForm = z.infer<typeof addSchema>;

function AddDocDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  const form = useForm<AddForm>({
    resolver: zodResolver(addSchema),
    defaultValues: {
      year: String(new Date().getFullYear() - 1),
      league_name: "",
      club_name: "",
      description: "",
    },
  });

  const handleSubmit = async (data: AddForm) => {
    if (!selectedFile) {
      toast.error("Please select a PDF file");
      return;
    }
    if (selectedFile.type !== "application/pdf") {
      toast.error("Only PDF files are accepted");
      return;
    }
    setUploading(true);
    try {
      const { url, fields, key } = await playersApi.myReleaseLetterUploadUrl(
        selectedFile.name,
        "application/pdf"
      );
      const formData = new FormData();
      Object.entries(fields).forEach(([k, v]) => formData.append(k, v));
      formData.append("file", selectedFile);
      const s3Res = await fetch(url, { method: "POST", body: formData });
      if (!s3Res.ok) throw new Error("Upload to S3 failed");

      await playersApi.createReleaseLetterEntry({
        s3_key: key,
        file_name: selectedFile.name,
        year: parseInt(data.year, 10),
        league_name: data.league_name,
        club_name: data.club_name,
        description: data.description || undefined,
      });

      queryClient.invalidateQueries({ queryKey: ["my-release-letters"] });
      toast.success("Release doc added to your history");
      onOpenChange(false);
      form.reset();
      setSelectedFile(null);
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setUploading(false);
    }
  };

  const currentYear = new Date().getFullYear();
  const years = Array.from({ length: currentYear - 1989 }, (_, i) => currentYear - i);

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!v) { form.reset(); setSelectedFile(null); }
        onOpenChange(v);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add release document</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground -mt-2">
          Add a release letter from a previous league or club to your personal history.
        </p>
        <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="rd-year">Last played year *</Label>
              <select
                id="rd-year"
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                {...form.register("year")}
              >
                {years.map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>
              {form.formState.errors.year && (
                <p className="text-xs text-destructive">{form.formState.errors.year.message}</p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="rd-league">League name *</Label>
              <Input
                id="rd-league"
                placeholder="e.g. Colombo District League"
                {...form.register("league_name")}
              />
              {form.formState.errors.league_name && (
                <p className="text-xs text-destructive">
                  {form.formState.errors.league_name.message}
                </p>
              )}
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="rd-club">Club name *</Label>
            <Input
              id="rd-club"
              placeholder="e.g. Colombo FC"
              {...form.register("club_name")}
            />
            {form.formState.errors.club_name && (
              <p className="text-xs text-destructive">
                {form.formState.errors.club_name.message}
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="rd-desc">Notes (optional)</Label>
            <Input
              id="rd-desc"
              placeholder="e.g. Mid-season release by mutual agreement"
              {...form.register("description")}
            />
          </div>

          <div className="space-y-1.5">
            <Label>Release document (PDF) *</Label>
            <div
              onClick={() => fileInputRef.current?.click()}
              className={cn(
                "flex items-center gap-3 p-3 rounded-lg border-2 border-dashed cursor-pointer transition-colors",
                selectedFile
                  ? "border-primary/40 bg-primary/5"
                  : "border-border hover:border-primary/30 hover:bg-muted/30"
              )}
            >
              <Upload className="h-4 w-4 text-muted-foreground shrink-0" />
              {selectedFile ? (
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate">{selectedFile.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {(selectedFile.size / 1024).toFixed(0)} KB
                  </p>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">Click to select a PDF file</p>
              )}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf"
              className="hidden"
              onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
            />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={uploading || !selectedFile}>
              {uploading ? "Uploading…" : "Add document"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Single release doc card
// ---------------------------------------------------------------------------

function DocCard({
  doc,
  onToggle,
  toggling,
}: {
  doc: PlayerDocumentRead;
  onToggle: () => void;
  toggling: boolean;
}) {
  const isInLeague = doc.source === "in_league";

  return (
    <div className="rounded-xl border border-border bg-card p-4 space-y-3">
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-9 h-9 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0">
            <CalendarDays className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-base font-semibold">{doc.year ?? "—"}</span>
              {isInLeague && (
                <span className="text-[10px] font-bold bg-primary/10 text-primary px-1.5 py-0.5 rounded">
                  WFL
                </span>
              )}
              {!doc.is_visible && (
                <span className="text-[10px] font-bold bg-muted text-muted-foreground px-1.5 py-0.5 rounded">
                  Private
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          {doc.file_url && (
            <a
              href={doc.file_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-primary transition-colors"
              onClick={(e) => e.stopPropagation()}
            >
              <ExternalLink className="h-3.5 w-3.5" />
              View
            </a>
          )}
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-xs text-muted-foreground"
            onClick={onToggle}
            disabled={toggling}
            title={doc.is_visible ? "Make private" : "Make visible"}
          >
            {doc.is_visible ? (
              <><EyeOff className="h-3.5 w-3.5 mr-1" /> Hide</>
            ) : (
              <><Eye className="h-3.5 w-3.5 mr-1" /> Show</>
            )}
          </Button>
        </div>
      </div>

      {/* Details */}
      <div className="flex flex-wrap gap-x-4 gap-y-1.5">
        {doc.league_name && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Trophy className="h-3 w-3 shrink-0" />
            {doc.league_name}
          </div>
        )}
        {doc.club_name && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Building2 className="h-3 w-3 shrink-0" />
            {doc.club_name}
          </div>
        )}
      </div>

      {doc.description && (
        <p className="text-xs text-muted-foreground">{doc.description}</p>
      )}

      <p className="text-xs text-muted-foreground/70">
        Added {formatDate(doc.created_at)}
        {isInLeague && " · Auto-generated from league release"}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

type Tab = "visible" | "private";

export default function MyDocsPage() {
  const [tab, setTab] = useState<Tab>("visible");
  const [addOpen, setAddOpen] = useState(false);
  const queryClient = useQueryClient();
  const { user, isSuperAdmin } = useCurrentUser();

  const { data: docs = [], isLoading } = useQuery<PlayerDocumentRead[]>({
    queryKey: ["my-release-letters"],
    queryFn: playersApi.myReleaseLetters,
    enabled: !!user?.player_id && !isSuperAdmin,
  });

  const toggleMutation = useMutation({
    mutationFn: (docId: number) => playersApi.toggleReleaseLetterVisibility(docId),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ["my-release-letters"] });
      toast.success(updated.is_visible ? "Document is now visible to admins" : "Document is now private");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const visible = docs.filter((d) => d.is_visible);
  const hidden = docs.filter((d) => !d.is_visible);
  const shown = tab === "visible" ? visible : hidden;

  if (isSuperAdmin) {
    return (
      <div>
        <PageHeader title="My Release Docs" description="Personal release history" />
        <p className="text-sm text-muted-foreground mt-4">
          Super admins do not have a personal player profile.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <PageHeader
        title="My Release Docs"
        description="Your personal release history — visible docs are shared with club and league admins"
        action={
          <Button size="sm" onClick={() => setAddOpen(true)} className="gap-1.5">
            <Plus className="h-4 w-4" />
            Add release doc
          </Button>
        }
      />

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border -mt-2">
        {(["visible", "private"] as Tab[]).map((t) => {
          const count = t === "visible" ? visible.length : hidden.length;
          return (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={cn(
                "flex items-center gap-1.5 px-4 py-2 text-sm font-medium -mb-px border-b-2 transition-colors",
                tab === t
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              )}
            >
              {t === "visible" ? (
                <Eye className="h-3.5 w-3.5" />
              ) : (
                <Lock className="h-3.5 w-3.5" />
              )}
              {t.charAt(0).toUpperCase() + t.slice(1)}
              {count > 0 && (
                <span className="text-[10px] font-bold bg-muted px-1.5 py-0.5 rounded-full text-muted-foreground">
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {tab === "private" && (
        <div className="flex items-start gap-2 rounded-lg bg-muted/50 border border-border p-3 text-xs text-muted-foreground">
          <Lock className="h-3.5 w-3.5 shrink-0 mt-0.5" />
          <span>
            Private documents are only visible to you. Click <strong>Show</strong> on any doc to make it visible to club and league admins.
          </span>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="rounded-xl border border-border bg-card p-4 animate-pulse">
              <div className="h-5 bg-muted rounded w-32 mb-2" />
              <div className="h-3 bg-muted rounded w-48" />
            </div>
          ))}
        </div>
      ) : shown.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border p-10 text-center">
          {tab === "visible" ? (
            <>
              <BookOpen className="h-7 w-7 text-muted-foreground mx-auto mb-3" />
              <p className="text-sm font-medium text-muted-foreground">No release docs yet</p>
              <p className="text-xs text-muted-foreground mt-1 mb-4">
                Docs from your releases within Wattala League are added automatically.
                You can also add external release letters from other leagues.
              </p>
              <Button size="sm" variant="outline" onClick={() => setAddOpen(true)} className="gap-1.5">
                <FilePlus className="h-4 w-4" />
                Add release doc
              </Button>
            </>
          ) : (
            <>
              <Lock className="h-7 w-7 text-muted-foreground mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">No private documents</p>
            </>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {shown.map((doc) => (
            <DocCard
              key={doc.id}
              doc={doc}
              onToggle={() => toggleMutation.mutate(doc.id)}
              toggling={toggleMutation.isPending && toggleMutation.variables === doc.id}
            />
          ))}
        </div>
      )}

      <AddDocDialog open={addOpen} onOpenChange={setAddOpen} />
    </div>
  );
}
