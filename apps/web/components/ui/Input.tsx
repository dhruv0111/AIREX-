import React, { forwardRef, InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

export interface FormFieldProps {
  label?: string;
  error?: string;
  hint?: string;
  required?: boolean;
  children: React.ReactNode;
  className?: string;
  htmlFor?: string;
}

export function FormField({
  label,
  error,
  hint,
  required,
  children,
  className = "",
  htmlFor,
}: FormFieldProps) {
  return (
    <div className={`space-y-1.5 ${className}`}>
      {label ? (
        <label
          htmlFor={htmlFor}
          className="block text-xs font-semibold text-slate-700 tracking-wide"
        >
          {label}
          {required ? <span className="text-danger ml-0.5">*</span> : null}
        </label>
      ) : null}
      {children}
      {hint && !error ? <p className="text-xs text-slate-500">{hint}</p> : null}
      {error ? <p className="text-xs font-medium text-danger">{error}</p> : null}
    </div>
  );
}

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  error?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className = "", error, ...props },
  ref,
) {
  return (
    <input
      ref={ref}
      className={`w-full rounded-lg border bg-white px-3.5 py-2 text-sm text-slate-900 placeholder:text-slate-400 shadow-sm transition focus:outline-none focus:ring-2 disabled:bg-slate-50 disabled:text-slate-500 disabled:cursor-not-allowed ${
        error
          ? "border-red-300 focus:border-red-500 focus:ring-red-200"
          : "border-slate-300 focus:border-brand-600 focus:ring-brand-100"
      } ${className}`}
      {...props}
    />
  );
});

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  error?: boolean;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { className = "", error, children, ...props },
  ref,
) {
  return (
    <select
      ref={ref}
      className={`w-full rounded-lg border bg-white px-3.5 py-2 text-sm text-slate-900 shadow-sm transition focus:outline-none focus:ring-2 disabled:bg-slate-50 disabled:text-slate-500 disabled:cursor-not-allowed ${
        error
          ? "border-red-300 focus:border-red-500 focus:ring-red-200"
          : "border-slate-300 focus:border-brand-600 focus:ring-brand-100"
      } ${className}`}
      {...props}
    >
      {children}
    </select>
  );
});

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { className = "", error, ...props },
  ref,
) {
  return (
    <textarea
      ref={ref}
      className={`w-full rounded-lg border bg-white px-3.5 py-2 text-sm text-slate-900 placeholder:text-slate-400 shadow-sm transition focus:outline-none focus:ring-2 disabled:bg-slate-50 disabled:text-slate-500 disabled:cursor-not-allowed ${
        error
          ? "border-red-300 focus:border-red-500 focus:ring-red-200"
          : "border-slate-300 focus:border-brand-600 focus:ring-brand-100"
      } ${className}`}
      {...props}
    />
  );
});
