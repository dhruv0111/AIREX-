"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";
import { logger } from "@/lib/logger";

interface ErrorBoundaryProps {
  children: ReactNode;
  /** Optional custom fallback UI; defaults to a branded error card. */
  fallback?: ReactNode;
  /** Logical label included in the error log for easier debugging. */
  scope?: string;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/**
 * Client error boundary that catches render errors in its subtree, logs them
 * through the structured logger (scope + component stack), and renders a
 * fallback instead of unmounting the whole app.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    logger.error("React render error", {
      scope: this.props.scope ?? "error-boundary",
      componentStack: info.componentStack,
    }, error);
  }

  render(): ReactNode {
    if (this.state.error) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div
          role="alert"
          className="m-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800"
        >
          <p className="font-semibold">Something went wrong</p>
          <p className="mt-1 font-mono text-xs">{this.state.error.message}</p>
          <p className="mt-2 text-xs text-red-600">
            Check the browser console for a logged <code>[AIREX:error]</code> entry with the full stack trace.
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}
