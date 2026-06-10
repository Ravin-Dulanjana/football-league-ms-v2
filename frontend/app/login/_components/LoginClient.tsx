"use client";

import { useState } from "react";
import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Eye, EyeOff, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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

// ---------------------------------------------------------------------------
// Step machine: login → (otp?) → dashboard or force-password
// ---------------------------------------------------------------------------

type Step = "login" | "otp" | "force_password";

// ---------------------------------------------------------------------------
// LoginContent uses useSearchParams() — must be wrapped in <Suspense>.
// Next.js 14 requires this because useSearchParams() causes a CSR bailout
// during static-page generation. The outer LoginPage provides the boundary.
// ---------------------------------------------------------------------------

function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectTo = searchParams.get("from") ?? "/dashboard";

  const [step, setStep] = useState<Step>("login");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  // ---------------------------------------------------------------------------
  // Login form
  // ---------------------------------------------------------------------------

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
        // Check if backend signaled MFA required
        if (body?.detail === "mfa_required" || body?.mfa_required) {
          setStep("otp");
          return;
        }
        toast.error(body?.detail ?? "Login failed. Check your credentials.");
        return;
      }

      // Check force_password_change flag embedded in response
      if (body?.force_password_change) {
        setStep("force_password");
        return;
      }

      // Normal login — redirect to intended destination
      router.push(redirectTo);
      router.refresh();
    } catch {
      toast.error("Connection error. Is the backend running?");
    } finally {
      setLoading(false);
    }
  };

  // ---------------------------------------------------------------------------
  // OTP form (MFA step)
  // ---------------------------------------------------------------------------

  const otpForm = useForm<OtpForm>({
    resolver: zodResolver(otpSchema),
    defaultValues: { otp: "" },
  });

  const onOtp = async (data: OtpForm) => {
    setLoading(true);
    // TODO: wire to the MFA challenge endpoint when backend supports it.
    // For now, Cognito MFA is handled client-side via Amplify or the direct SDK.
    toast.info(`OTP submitted: ${data.otp} — MFA endpoint not yet wired`);
    setLoading(false);
  };

  // ---------------------------------------------------------------------------
  // Force password change form
  // ---------------------------------------------------------------------------

  const forcePasswordForm = useForm<ForcePasswordForm>({
    resolver: zodResolver(forcePasswordSchema),
    defaultValues: { new_password: "", confirm_password: "" },
  });

  const onForcePassword = async (data: ForcePasswordForm) => {
    setLoading(true);
    // TODO: wire to backend when Cognito new-password challenge is implemented.
    toast.info("Password change — backend endpoint not yet wired");
    setLoading(false);
    void data;
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="w-full max-w-sm space-y-6">

        {/* Brand mark */}
        <div className="text-center space-y-3">
          <div className="flex justify-center">
            <Image
              src="/logo.png"
              alt="Wattala Football League"
              width={88}
              height={88}
              className="rounded-full"
              priority
            />
          </div>
          <div className="space-y-1">
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">
              Wattala Football League
            </h1>
            <p className="text-sm text-muted-foreground">
              {step === "login" && "Sign in to your account"}
              {step === "otp" && "Enter your verification code"}
              {step === "force_password" && "Set a new password to continue"}
            </p>
          </div>
        </div>

        <Card className="border-border">
          <CardHeader className="pb-4">
            <CardTitle className="text-base">
              {step === "login" && "Sign in"}
              {step === "otp" && "Two-factor verification"}
              {step === "force_password" && "Change your password"}
            </CardTitle>
            <CardDescription>
              {step === "login" && "Enter your email and password"}
              {step === "otp" && "We sent a code to your registered device"}
              {step === "force_password" && "Your administrator has reset your password"}
            </CardDescription>
          </CardHeader>

          <CardContent>
            {/* Step: login */}
            {step === "login" && (
              <form onSubmit={loginForm.handleSubmit(onLogin)} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
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

                <div className="space-y-2">
                  <Label htmlFor="password">Password</Label>
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

                <Button type="submit" className="w-full" disabled={loading}>
                  {loading ? (
                    <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Signing in…</>
                  ) : (
                    "Sign in"
                  )}
                </Button>
              </form>
            )}

            {/* Step: OTP */}
            {step === "otp" && (
              <form onSubmit={otpForm.handleSubmit(onOtp)} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="otp">Verification code</Label>
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
                  {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  Verify
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
                <div className="space-y-2">
                  <Label htmlFor="new_password">New password</Label>
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

                <div className="space-y-2">
                  <Label htmlFor="confirm_password">Confirm new password</Label>
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
                  {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  Set new password
                </Button>
              </form>
            )}
          </CardContent>
        </Card>

        <p className="text-center text-xs text-muted-foreground">
          Wattala Football League Management System v2
        </p>
      </div>
    </div>
  );
}

export { LoginContent };
