import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { ErrorBoundary } from "@/components/ErrorBoundary";

export const metadata: Metadata = {
  title: "AIREX — AI Reliability, Evaluation & Observability Platform",
  description: "Automated evaluation, testing, monitoring and benchmarking for AI applications.",
};

const EARLY_ERROR_HANDLER = `(function () {
  // Installed in <head> so it runs BEFORE any webpack chunks load. Captures
  // module-load/runtime errors (e.g. stale-chunk "options.factory" failures)
  // that happen before React hydrates. Hands off to the full logger once
  // Providers sets window.__AIREX_LOGGER_ACTIVE.
  function ser(e) {
    if (e instanceof Error) return { name: e.name, message: e.message, stack: e.stack };
    try { return { message: String(e) }; } catch (_) { return { message: "unknown" }; }
  }
  function log(ev, kind) {
    if (window.__AIREX_LOGGER_ACTIVE) return;
    console.error("[AIREX:early] " + kind, JSON.stringify({
      ts: new Date().toISOString(),
      level: "error",
      scope: "window-early",
      kind: kind,
      url: location.href,
      err: ser(ev.error || ev.reason || new Error(ev.message || "Unknown error"))
    }));
  }
  window.addEventListener("error", function (ev) { log(ev, "uncaught-error"); });
  window.addEventListener("unhandledrejection", function (ev) { log(ev, "unhandled-rejection"); });
})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <script dangerouslySetInnerHTML={{ __html: EARLY_ERROR_HANDLER }} />
      </head>
      <body>
        <ErrorBoundary scope="root-layout">
          <Providers>{children}</Providers>
        </ErrorBoundary>
      </body>
    </html>
  );
}
