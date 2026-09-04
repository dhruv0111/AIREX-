import React from "react";

export type BadgeVariant =
  | "brand"
  | "success"
  | "warning"
  | "danger"
  | "neutral"
  | "info";

export type BadgeSize = "sm" | "md";

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  size?: BadgeSize;
  dot?: boolean;
  className?: string;
}

const badgeStyles: Record<BadgeVariant, { container: string; dot: string }> = {
  brand: {
    container: "bg-brand-50 text-brand-700 border-brand-200",
    dot: "bg-brand-500",
  },
  success: {
    container: "bg-emerald-50 text-emerald-700 border-emerald-200",
    dot: "bg-emerald-500",
  },
  warning: {
    container: "bg-amber-50 text-amber-800 border-amber-200",
    dot: "bg-amber-500",
  },
  danger: {
    container: "bg-rose-50 text-rose-700 border-rose-200",
    dot: "bg-rose-500",
  },
  neutral: {
    container: "bg-slate-100 text-slate-700 border-slate-200",
    dot: "bg-slate-400",
  },
  info: {
    container: "bg-sky-50 text-sky-700 border-sky-200",
    dot: "bg-sky-500",
  },
};

const sizeStyles: Record<BadgeSize, string> = {
  sm: "px-2 py-0.5 text-[11px] font-medium",
  md: "px-2.5 py-1 text-xs font-semibold",
};

export function Badge({
  children,
  variant = "neutral",
  size = "sm",
  dot = false,
  className = "",
}: BadgeProps) {
  const style = badgeStyles[variant] || badgeStyles.neutral;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border ${style.container} ${sizeStyles[size]} ${className}`}
    >
      {dot ? (
        <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
      ) : null}
      {children}
    </span>
  );
}

export function StatusBadge({ status }: { status?: string | null }) {
  if (!status) return <Badge variant="neutral">—</Badge>;

  const s = status.toUpperCase();

  if (s === "COMPLETED" || s === "ACTIVE" || s === "HEALTHY" || s === "APPROVED" || s === "CONNECTED" || s === "PASS") {
    return (
      <Badge variant="success" dot>
        {status}
      </Badge>
    );
  }

  if (s === "RUNNING" || s === "COLLECTING_EVIDENCE" || s === "IN_PROGRESS" || s === "PROCESSING") {
    return (
      <Badge variant="brand" dot className="animate-pulse">
        {status}
      </Badge>
    );
  }

  if (s === "WARNING" || s === "DEGRADED" || s === "CONDITIONALLY_APPROVED" || s === "STALE" || s === "QUEUED" || s === "PENDING") {
    return (
      <Badge variant="warning" dot>
        {status}
      </Badge>
    );
  }

  if (s === "FAILED" || s === "BLOCKED" || s === "REJECTED" || s === "ERROR" || s === "FAIL" || s === "UNREADY") {
    return (
      <Badge variant="danger" dot>
        {status}
      </Badge>
    );
  }

  return <Badge variant="neutral">{status}</Badge>;
}
