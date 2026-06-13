"use client";

import { useState } from "react";
import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { ArrowRight, Eye, EyeOff, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Zod schemas
// ---------------------------------------------------------------------------

const loginSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

const otpSchema = z.object({
  otp: z.string().length(6, "OTP must be exactly 6 digits"),
});

const forcePasswordSchema = z
  .object({
    new_password: z.string().min(8, "Password must be at least 8 characters"),
    confirm_password: z.string(),
  })
  .refine((d) => d.new_password === d.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

type LoginForm = z.infer<typeof loginSchema>;
type OtpForm = z.infer<typeof otpSchema>;
type ForcePasswordForm = z.infer<typeof forcePasswordSchema>;

type Step = "login" | "otp" | "force_password";

interface ChallengeState {
  email: string;
  session: string;
}

// ---------------------------------------------------------------------------
// LoginContent
// ---------------------------------------------------------------------------

function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectTo = searchParams.get("from") ?? "/dashboard";

  const [step, setStep] = useState<Step>("login");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [challenge, setChallenge] = useState<ChallengeState | null>(null);

  // Login form
  const loginForm = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const onLogin = async (data: LoginForm) => {
    setLoading(true);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      const body = await res.json();
      if (!res.ok) {
        if (body?.detail === "mfa_required" || body?.mfa_required) {
          setStep("otp");
          return;
        }
        toast.error(body?.detail ?? "Login failed. Check your credentials.");
        return;
      }
      if (body?.challenge === "NEW_PASSWORD_REQUIRED") {
        setChallenge({ email: data.email, session: body.session });
        setStep("force_password");
        return;
      }
      router.push(redirectTo);
      router.refresh();
    } catch {
      toast.error("Connection error. Is the backend running?");
    } finally {
      setLoading(false);
    }
  };

  // OTP form
  const otpForm = useForm<OtpForm>({
    resolver: zodResolver(otpSchema),
    defaultValues: { otp: "" },
  });

  const onOtp = async (data: OtpForm) => {
    setLoading(true);
    toast.info(`OTP submitted: ${data.otp} — MFA endpoint not yet wired`);
    setLoading(false);
  };

  // Force password form
  const forcePasswordForm = useForm<ForcePasswordForm>({
    resolver: zodResolver(forcePasswordSchema),
    defaultValues: { new_password: "", confirm_password: "" },
  });

  const onForcePassword = async (data: ForcePasswordForm) => {
    if (!challenge) {
      toast.error("Session lost — please sign in again.");
      setStep("login");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch("/api/auth/complete-challenge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: challenge.email,
          new_password: data.new_password,
          session: challenge.session,
        }),
      });
      const body = await res.json();
      if (!res.ok) {
        toast.error(body?.detail ?? "Failed to set new password. Please try again.");
        if (res.status === 401) {
          setStep("login");
          setChallenge(null);
        }
        return;
      }
      toast.success("Password updated — you're now signed in.");
      router.push(redirectTo);
      router.refresh();
    } catch {
      toast.error("Connection error. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="w-full max-w-[400px]">

        {/* Crest + identity */}
        <div className="flex flex-col items-center text-center mb-8">
          <Image
            src="/logo.png"
            alt="Wattala Football League"
            width={76}
            height={76}
            className="rounded-full mb-4"
            priority
          />
          <p className="eyebrow mb-2">Est. 1949</p>
          <h1 className="font-serif text-2xl font-semibold tracking-tight text-foreground">
            Wattala Football League
          </h1>
        </div>

        {/* Card */}
        <div className="card-surface px-8 py-8">

          {/* Card heading */}
          <div className="mb-6">
            <h2 className="text-base font-bold text-foreground">
              {step === "login" && "Sign in"}
              {step === "otp" && "Two-factor verification"}
              {step === "force_password" && "Choose a new password"}
            </h2>
            {step !== "login" && (
              <p className="text-xs text-muted-foreground mt-1">
                {step === "otp" && "Enter the code sent to your registered device"}
                {step === "force_password" && "Your account requires a password change before you can continue"}
              </p>
            )}
          </div>

          {/* Hairline */}
          <div className="h-px bg-border mb-6" />

          {/* Step: login */}
          {step === "login" && (
            <form onSubmit={loginForm.handleSubmit(onLogin)} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="email" className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Email
                </Label>
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  placeholder="admin@example.com"
                  {...loginForm.register("email")}
                  className={cn(loginForm.formState.errors.email && "border-destructive")}
                />
                {loginForm.formState.errors.email && (
                  <p className="text-xs text-destructive">{loginForm.formState.errors.email.message}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="password" className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Password
                </Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    placeholder="••••••••"
                    {...loginForm.register("password")}
                    className={cn(
                      "pr-10",
                      loginForm.formState.errors.password && "border-destructive"
                    )}
                  />
                  <button
                    type="button"
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                    onClick={() => setShowPassword((v) => !v)}
                    tabIndex={-1}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {loginForm.formState.errors.password && (
                  <p className="text-xs text-destructive">{loginForm.formState.errors.password.message}</p>
                )}
              </div>

              <Button type="submit" className="w-full mt-2" disabled={loading}>
                {loading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <>
                    Sign in
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </Button>
            </form>
          )}

          {/* Step: OTP */}
          {step === "otp" && (
            <form onSubmit={otpForm.handleSubmit(onOtp)} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="otp" className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Verification code
                </Label>
                <Input
                  id="otp"
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  autoComplete="one-time-code"
                  placeholder="000000"
                  {...otpForm.register("otp")}
                  className="text-center tracking-widest text-lg font-mono"
                />
                {otpForm.formState.errors.otp && (
                  <p className="text-xs text-destructive">{otpForm.formState.errors.otp.message}</p>
                )}
              </div>

              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <><ArrowRight className="h-4 w-4" /> Verify</>}
              </Button>
              <button
                type="button"
                className="w-full text-xs text-muted-foreground hover:text-foreground transition-colors"
                onClick={() => setStep("login")}
              >
                Back to sign in
              </button>
            </form>
          )}

          {/* Step: force password change */}
          {step === "force_password" && (
            <form onSubmit={forcePasswordForm.handleSubmit(onForcePassword)} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="new_password" className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  New password
                </Label>
                <Input
                  id="new_password"
                  type="password"
                  autoComplete="new-password"
                  placeholder="Min. 8 characters"
                  {...forcePasswordForm.register("new_password")}
                />
                {forcePasswordForm.formState.errors.new_password && (
                  <p className="text-xs text-destructive">{forcePasswordForm.formState.errors.new_password.message}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="confirm_password" className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Confirm new password
                </Label>
                <Input
                  id="confirm_password"
                  type="password"
                  autoComplete="new-password"
                  placeholder="Repeat your new password"
                  {...forcePasswordForm.register("confirm_password")}
                />
                {forcePasswordForm.formState.errors.confirm_password && (
                  <p className="text-xs text-destructive">{forcePasswordForm.formState.errors.confirm_password.message}</p>
                )}
              </div>

              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <><ArrowRight className="h-4 w-4" /> Set password</>}
              </Button>
            </form>
          )}
        </div>

        {/* Footer */}
        <p className="text-center text-xs text-muted-foreground mt-6">
          Management System v2 · Secured access
        </p>
      </div>
    </div>
  );
}

export { LoginContent };
