import { Suspense } from "react";
import { LoginContent } from "./_components/LoginClient";

// The Suspense boundary must be in a server component. If it lives inside a
// "use client" file, Next.js does not treat it as a server-side boundary and
// still errors with "useSearchParams() should be wrapped in a suspense" during
// static page generation.
export default function LoginPage() {
  return (
    <Suspense>
      <LoginContent />
    </Suspense>
  );
}
