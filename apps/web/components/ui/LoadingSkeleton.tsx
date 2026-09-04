import React from "react";

export function LoadingSkeleton({
  className = "h-4 w-full",
}: {
  className?: string;
}) {
  return (
    <div
      className={`animate-pulse rounded-md bg-slate-200/80 ${className}`}
    />
  );
}

export function TableSkeleton({ rows = 4, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div className="w-full space-y-3 py-2">
      <div className="flex gap-4 border-b border-slate-200 pb-3">
        {Array.from({ length: cols }).map((_, i) => (
          <div key={i} className="h-4 flex-1 animate-pulse rounded bg-slate-200" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex gap-4 py-2 border-b border-slate-100">
          {Array.from({ length: cols }).map((_, c) => (
            <div
              key={c}
              className="h-4 flex-1 animate-pulse rounded bg-slate-100"
            />
          ))}
        </div>
      ))}
    </div>
  );
}

export function MetricSkeleton() {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-card space-y-3 animate-pulse">
      <div className="h-3 w-20 bg-slate-200 rounded" />
      <div className="h-7 w-32 bg-slate-200 rounded" />
      <div className="h-3 w-24 bg-slate-100 rounded" />
    </div>
  );
}
