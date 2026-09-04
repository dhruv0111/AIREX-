import React from "react";

interface CardProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "title"> {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  bodyClassName?: string;
}

export function Card({
  title,
  subtitle,
  action,
  children,
  className = "",
  bodyClassName = "",
  ...props
}: CardProps) {
  return (
    <section
      className={`rounded-xl border border-slate-200 bg-white text-slate-900 shadow-card transition-all ${className}`}
      {...props}
    >
      {title || action ? (
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <div>
            {typeof title === "string" ? (
              <h2 className="text-base font-semibold text-slate-900 tracking-tight">
                {title}
              </h2>
            ) : (
              title
            )}
            {subtitle ? (
              <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>
            ) : null}
          </div>
          {action ? <div className="flex items-center gap-2">{action}</div> : null}
        </div>
      ) : null}
      <div className={`p-6 ${bodyClassName}`}>{children}</div>
    </section>
  );
}

interface MetricCardProps {
  label: string;
  value: React.ReactNode;
  subvalue?: React.ReactNode;
  badge?: React.ReactNode;
  icon?: React.ReactNode;
  accent?: "brand" | "success" | "warning" | "danger" | "neutral";
  className?: string;
  testId?: string;
}

export function MetricCard({
  label,
  value,
  subvalue,
  badge,
  icon,
  accent = "neutral",
  className = "",
  testId,
}: MetricCardProps) {
  const accentBorder = {
    brand: "border-l-4 border-l-brand-600",
    success: "border-l-4 border-l-emerald-500",
    warning: "border-l-4 border-l-amber-500",
    danger: "border-l-4 border-l-rose-500",
    neutral: "",
  }[accent];

  return (
    <div
      data-testid={testId}
      className={`rounded-xl border border-slate-200 bg-white p-5 shadow-card ${accentBorder} ${className}`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          {label}
        </span>
        {badge || icon || null}
      </div>
      <div className="mt-2 text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
        {value}
      </div>
      {subvalue ? (
        <div className="mt-1 text-xs font-medium text-slate-500">{subvalue}</div>
      ) : null}
    </div>
  );
}
