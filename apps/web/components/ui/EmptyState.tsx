import React from "react";

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className = "",
}: EmptyStateProps) {
  return (
    <div
      className={`rounded-xl border border-dashed border-slate-300 bg-slate-50/50 p-8 sm:p-12 text-center transition-all ${className}`}
    >
      <div className="mx-auto flex max-w-sm flex-col items-center">
        {icon ? (
          <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-white text-slate-400 shadow-sm border border-slate-200">
            {icon}
          </div>
        ) : (
          <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-white text-slate-400 shadow-sm border border-slate-200 font-bold text-lg">
            ✦
          </div>
        )}
        <h3 className="text-base font-semibold text-slate-900 tracking-tight">
          {title}
        </h3>
        {description ? (
          <p className="mt-1.5 text-xs text-slate-500 leading-relaxed">
            {description}
          </p>
        ) : null}
        {action ? <div className="mt-5">{action}</div> : null}
      </div>
    </div>
  );
}
