"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@airex/api-client";

export function SystemHealthBanner() {
  const readinessQuery = useQuery({
    queryKey: ["system-readiness"],
    queryFn: async () => {
      try {
        const res = await api.getSystemReadiness();
        return res?.data ?? res ?? null;
      } catch {
        return null;
      }
    },
    refetchInterval: 30000,
  });

  const readiness = readinessQuery.data;
  if (!readiness) return null;

  if (readiness.overall_status === "HEALTHY") {
    return null;
  }

  if (readiness.overall_status === "DEGRADED") {
    return (
      <div className="bg-amber-950/70 border-b border-amber-800/80 px-4 py-2 text-xs text-amber-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-semibold px-2 py-0.5 rounded bg-amber-900/80 text-amber-300 uppercase tracking-wider text-[10px]">
            Degraded Mode
          </span>
          <span>
            AIREX is operating with partial redundancy. Background workers or secondary components are degraded, but evaluation records remain safe.
          </span>
        </div>
        <a
          href="/admin/system"
          className="text-amber-400 hover:underline font-medium text-xs whitespace-nowrap ml-4"
        >
          View System Diagnostics &rarr;
        </a>
      </div>
    );
  }

  if (readiness.overall_status === "UNREADY") {
    return (
      <div className="bg-red-950/80 border-b border-red-800 px-4 py-2.5 text-xs text-red-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-bold px-2 py-0.5 rounded bg-red-900 text-red-100 uppercase tracking-wider text-[10px]">
            Platform Alert
          </span>
          <span>
            Critical platform dependencies are disconnected. New background executions and evaluation runs may fail.
          </span>
        </div>
        <a
          href="/admin/system"
          className="text-red-300 hover:underline font-bold text-xs whitespace-nowrap ml-4"
        >
          System Diagnostics &rarr;
        </a>
      </div>
    );
  }

  return null;
}
