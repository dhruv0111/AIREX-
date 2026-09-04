import React from "react";

export type AlertKind = "error" | "success" | "warning" | "info";

interface AlertProps {
  kind: AlertKind;
  title?: string;
  children: React.ReactNode;
  className?: string;
  onClose?: () => void;
}

const alertStyles: Record<AlertKind, { container: string; icon: string; title: string }> = {
  error: {
    container: "border-red-200 bg-red-50/90 text-red-800",
    icon: "text-red-500",
    title: "text-red-900",
  },
  success: {
    container: "border-emerald-200 bg-emerald-50/90 text-emerald-800",
    icon: "text-emerald-500",
    title: "text-emerald-900",
  },
  warning: {
    container: "border-amber-200 bg-amber-50/90 text-amber-800",
    icon: "text-amber-500",
    title: "text-amber-900",
  },
  info: {
    container: "border-indigo-200 bg-indigo-50/90 text-indigo-800",
    icon: "text-indigo-500",
    title: "text-indigo-900",
  },
};

export function Alert({
  kind = "info",
  title,
  children,
  className = "",
  onClose,
}: AlertProps) {
  const style = alertStyles[kind];

  return (
    <div
      role="alert"
      className={`relative rounded-lg border p-4 text-sm shadow-sm transition-all ${style.container} ${className}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          {title ? (
            <h4 className={`font-semibold mb-1 text-sm ${style.title}`}>
              {title}
            </h4>
          ) : null}
          <div className="leading-relaxed">{children}</div>
        </div>
        {onClose ? (
          <button
            type="button"
            onClick={onClose}
            aria-label="Close alert"
            className="text-slate-400 hover:text-slate-700 p-1 -mr-1 -mt-1 rounded hover:bg-black/5"
          >
            ✕
          </button>
        ) : null}
      </div>
    </div>
  );
}
