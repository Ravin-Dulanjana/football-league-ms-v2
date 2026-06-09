"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Eye, EyeOff, KeyRound, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

async function changePassword(oldPassword: string, newPassword: string): Promise<void> {
  const res = await fetch(
    `/api/proxy?path=${encodeURIComponent("/auth/change-password")}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
    }
  );
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail ?? `Request failed (${res.status})`);
  }
}

const schema = z
  .object({
    old_password: z.string().min(1, "Current password is required"),
    new_password: z.string().min(8, "New password must be at least 8 characters"),
    confirm_password: z.string(),
  })
  .refine((d) => d.new_password === d.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

type Form = z.infer<typeof schema>;

function PasswordInput({
  id,
  show,
  onToggle,
  error,
  ...props
}: React.ComponentPropsWithoutRef<"input"> & {
  id: string;
  show: boolean;
  onToggle: () => void;
  error?: string;
}) {
  return (
    <div className="space-y-1.5">
      <div className="relative">
        <Input
          id={id}
          type={show ? "text" : "password"}
          className={cn("pr-10", error && "border-destructive")}
          {...props}
        />
        <button
          type="button"
          tabIndex={-1}
          onClick={onToggle}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
        >
          {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}

export default function PasswordPage() {
  const [loading, setLoading] = useState(false);
  const [showOld, setShowOld] = useState(false);
  const [showNew, setShowNew] = useState(false);

  const form = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: { old_password: "", new_password: "", confirm_password: "" },
  });

  const onSubmit = async (data: Form) => {
    setLoading(true);
    try {
      await changePassword(data.old_password, data.new_password);
      toast.success("Password changed successfully");
      form.reset();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to change password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-md">
      <div className="mb-6">
        <h1 className="text-xl font-semibold">Change password</h1>
        <p className="text-sm text-muted-foreground mt-1">Update your account password</p>
      </div>

      <Card>
        <CardHeader className="pb-4">
          <CardTitle className="text-base flex items-center gap-2">
            <KeyRound className="h-4 w-4" />
            Set a new password
          </CardTitle>
          <CardDescription>
            Must be at least 8 characters. You&apos;ll need to sign in again after changing it.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="old_password">Current password</Label>
              <PasswordInput
                id="old_password"
                show={showOld}
                onToggle={() => setShowOld((v) => !v)}
                autoComplete="current-password"
                error={form.formState.errors.old_password?.message}
                {...form.register("old_password")}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="new_password">New password</Label>
              <PasswordInput
                id="new_password"
                show={showNew}
                onToggle={() => setShowNew((v) => !v)}
                autoComplete="new-password"
                error={form.formState.errors.new_password?.message}
                {...form.register("new_password")}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="confirm_password">Confirm new password</Label>
              <div className="space-y-1.5">
                <Input
                  id="confirm_password"
                  type="password"
                  autoComplete="new-password"
                  className={cn(form.formState.errors.confirm_password && "border-destructive")}
                  {...form.register("confirm_password")}
                />
                {form.formState.errors.confirm_password && (
                  <p className="text-xs text-destructive">
                    {form.formState.errors.confirm_password.message}
                  </p>
                )}
              </div>
            </div>

            <Button type="submit" disabled={loading} className="w-full">
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Changing password…
                </>
              ) : (
                "Change password"
              )}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
