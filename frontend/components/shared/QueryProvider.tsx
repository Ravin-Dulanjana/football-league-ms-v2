"use client";

// ---------------------------------------------------------------------------
// QueryProvider wraps the app in TanStack Query's QueryClientProvider.
//
// Why a separate component? Next.js app router server components can't use
// React context. We need the QueryClientProvider at the root layout, but the
// root layout is (and must remain) a server component for performance.
// The pattern: root layout → <QueryProvider> (client) → children (server or client).
// ---------------------------------------------------------------------------

import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";

export function QueryProvider({ children }: { children: React.ReactNode }) {
  // useState ensures each browser session gets its own QueryClient instance
  // (avoids sharing state between server renders in development)
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // Data is considered fresh for 60s — prevents waterfall re-fetches
            // when multiple components on the same page request the same data.
            staleTime: 60 * 1000,
            // Retry once on failure (e.g. transient network issues)
            // but not for 401/403 (auth errors — failing faster is better)
            retry: (failureCount, error) => {
              if (error instanceof Error && error.message === "Unauthorized")
                return false;
              return failureCount < 1;
            },
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {process.env.NODE_ENV === "development" && (
        <ReactQueryDevtools initialIsOpen={false} />
      )}
    </QueryClientProvider>
  );
}
