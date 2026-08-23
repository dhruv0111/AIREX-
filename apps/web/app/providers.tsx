"use client";

import { QueryClient, QueryClientProvider, QueryCache } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ApiClientError } from "@airex/api-client";
import { installGlobalErrorHandlers, logger, type LogContext } from "@/lib/logger";

/** True for unexpected failures (network / 5xx) that warrant an `error` log. */
function isServerError(error: unknown): boolean {
  return !(error instanceof ApiClientError) || error.status >= 500;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        queryCache: new QueryCache({
          onError: (error, query) => {
            const ctx: LogContext = {
              scope: "react-query",
              queryKey: JSON.stringify(query.queryKey),
            };
            if (isServerError(error)) {
              logger.error("React Query request failed", ctx, error);
            } else {
              // Expected client errors (4xx: validation, auth, not-found) — log as
              // warn to keep the console clean; pages surface these to users in UI.
              logger.warn("React Query request rejected", ctx, error);
            }
          },
        }),
      }),
  );

  // Log uncaught errors / unhandled promise rejections (e.g. webpack module-load
  // failures) to the console for easier debugging.
  useEffect(() => installGlobalErrorHandlers(), []);

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
