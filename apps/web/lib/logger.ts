/**
 * Structured client-side logger for the AIREX web app.
 *
 * Every log line is emitted as a JSON entry so it can be grepped/filtered in the
 * browser devtools console, plus a human-readable prefix. Levels are controlled
 * by `NEXT_PUBLIC_LOG_LEVEL` (debug | info | warn | error), defaulting to "debug"
 * in development.
 *
 * Usage:
 *   import { logger } from "@/lib/logger";
 *   logger.info("Models fetched", { scope: "models-page", count: data.length });
 *   logger.error("Failed to load models", { scope: "models-page" }, error);
 */
type LogLevel = "debug" | "info" | "warn" | "error";

const LOG_LEVELS: Record<LogLevel, number> = { debug: 10, info: 20, warn: 30, error: 40 };

const THRESHOLD: number = (() => {
  const configured = process.env.NEXT_PUBLIC_LOG_LEVEL as LogLevel | undefined;
  return (configured && LOG_LEVELS[configured]) || LOG_LEVELS.debug;
})();

export interface LogContext {
  /** Logical area of the app emitting the log (e.g. "dashboard", "react-query"). */
  scope?: string;
  [key: string]: unknown;
}

/** Normalize any thrown value into a serializable object (keeps stack + custom fields). */
export function serializeError(err: unknown): Record<string, unknown> {
  if (err instanceof Error) {
    const out: Record<string, unknown> = {
      name: err.name || "Error",
      message: err.message || String(err),
      stack: err.stack,
    };
    // Preserve known custom error fields (ApiClientError code/status/requestId, etc.)
    const extra = err as unknown as Record<string, unknown>;
    for (const key of ["code", "status", "requestId"]) {
      if (extra[key] !== undefined) out[key] = extra[key];
    }
    return out;
  }
  if (err !== null && typeof err === "object") {
    const obj = err as Record<string, unknown>;
    return {
      name: (obj.name as string) ?? "Error",
      message: (obj.message as string) ?? JSON.stringify(obj),
      ...obj,
    };
  }
  try {
    return { name: "Error", message: String(err) };
  } catch {
    return { name: "Error", message: "Unknown error (unserializable)" };
  }
}

function emit(level: LogLevel, message: string, ctx?: LogContext, err?: unknown): void {
  if (LOG_LEVELS[level] < THRESHOLD) return;

  const entry = {
    ts: new Date().toISOString(),
    level,
    scope: ctx?.scope ?? "app",
    message,
    ...(ctx ?? {}),
    ...(err !== undefined ? { err: serializeError(err) } : {}),
    url: typeof window !== "undefined" ? window.location.href : undefined,
  };

  const sink =
    level === "error"
      ? console.error
      : level === "warn"
        ? console.warn
        : level === "debug"
          ? console.debug
          : console.info;

  // Human-readable prefix for quick scanning in devtools.
  sink(`[AIREX:${level}]`, message, ...(err !== undefined ? [serializeError(err)] : []));
  // Structured JSON line for greppable, machine-friendly debugging.
  sink(JSON.stringify(entry));
}

export const logger = {
  debug: (message: string, ctx?: LogContext): void => emit("debug", message, ctx),
  info: (message: string, ctx?: LogContext): void => emit("info", message, ctx),
  warn: (message: string, ctx?: LogContext, err?: unknown): void => emit("warn", message, ctx, err),
  error: (message: string, ctx?: LogContext, err?: unknown): void => emit("error", message, ctx, err),
};

/** Compact single-line error string, useful for messages/Alert UIs. */
export function formatError(err: unknown): string {
  const e = serializeError(err);
  return `${e.name ?? "Error"}: ${e.message ?? ""}`.trim();
}

declare global {
  interface Window {
    /** Set once the full structured logger's handlers are active (see logger.ts). */
    __AIREX_LOGGER_ACTIVE?: boolean;
  }
}

/**
 * Register global browser handlers so uncaught errors and unhandled promise
 * rejections (e.g. webpack module-load failures) are logged with full context.
 * Returns a cleanup function. Safe to call on the client only.
 *
 * Marks `window.__AIREX_LOGGER_ACTIVE` so the early inline handler installed in
 * `app/layout.tsx` (which runs before React hydrates) hands off to this richer
 * logger instead of double-reporting.
 */
export function installGlobalErrorHandlers(): () => void {
  if (typeof window === "undefined") return () => undefined;

  // Hand off from the early inline handler once the full logger is ready.
  window.__AIREX_LOGGER_ACTIVE = true;

  const onError = (event: ErrorEvent): void => {
    logger.error(
      "Uncaught window error",
      { scope: "window", source: event.filename, line: event.lineno, col: event.colno },
      event.error ?? new Error(event.message),
    );
  };

  const onRejection = (event: PromiseRejectionEvent): void => {
    logger.error("Unhandled promise rejection", { scope: "window" }, event.reason);
  };

  window.addEventListener("error", onError);
  window.addEventListener("unhandledrejection", onRejection);

  return () => {
    window.removeEventListener("error", onError);
    window.removeEventListener("unhandledrejection", onRejection);
  };
}
