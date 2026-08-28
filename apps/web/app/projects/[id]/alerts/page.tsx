"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Alert } from "@/components/ui/Alert";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

const SEVERITY_COLORS: Record<string, string> = {
  INFO: "bg-sky-100 text-sky-800",
  LOW: "bg-emerald-100 text-emerald-800",
  MEDIUM: "bg-amber-100 text-amber-800",
  HIGH: "bg-orange-100 text-orange-800",
  CRITICAL: "bg-red-100 text-red-800",
};

const STATUS_COLORS: Record<string, string> = {
  TRIGGERED: "bg-red-100 text-red-800",
  ACKNOWLEDGED: "bg-amber-100 text-amber-800",
  RESOLVED: "bg-green-100 text-green-800",
  NORMAL: "bg-slate-100 text-slate-700",
};

type Tab = "active" | "history";

export default function AlertsPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("active");
  const [error, setError] = useState<string | null>(null);

  const alertsQuery = useQuery({
    queryKey: ["alerts", projectId],
    queryFn: () => api.listAlerts(projectId),
  });

  const ackMutation = useMutation({
    mutationFn: (alertId: string) => api.acknowledgeAlert(projectId, alertId),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["alerts", projectId] });
    },
    onError: (e) => setError(e instanceof ApiClientError ? e.message : "Failed to acknowledge alert"),
  });

  const alerts = alertsQuery.data ?? [];
  const active = alerts.filter((a) => a.status === "TRIGGERED" || a.status === "ACKNOWLEDGED");
  const history = alerts.filter((a) => a.status === "RESOLVED");
  const displayed = tab === "active" ? active : history;

  return (
    <AppShell>
      <div className="flex flex-col gap-6">
        <div>
          <Link href={`/projects/${projectId}/observability`} className="text-sm text-brand hover:underline">
            ← Observability
          </Link>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-2xl font-bold text-slate-900">Alerts</h1>
              <p className="text-sm text-slate-500">Production incidents produced by the alert engine.</p>
            </div>
            <nav className="flex gap-2 text-sm">
              <button
                onClick={() => setTab("active")}
                className={`rounded-md border px-3 py-1.5 ${
                  tab === "active" ? "border-brand bg-brand text-white" : "border-slate-200 text-slate-600 hover:border-brand hover:text-brand"
                }`}
              >
                Active ({active.length})
              </button>
              <button
                onClick={() => setTab("history")}
                className={`rounded-md border px-3 py-1.5 ${
                  tab === "history" ? "border-brand bg-brand text-white" : "border-slate-200 text-slate-600 hover:border-brand hover:text-brand"
                }`}
              >
                History ({history.length})
              </button>
              <Link
                href={`/projects/${projectId}/alerts/rules`}
                className="rounded-md border border-slate-200 px-3 py-1.5 text-slate-600 hover:border-brand hover:text-brand"
              >
                Rules
              </Link>
            </nav>
          </div>
        </div>

        {error ? <Alert kind="error">{error}</Alert> : null}

        {alertsQuery.isLoading ? (
          <Card><p className="text-sm text-slate-400">Loading alerts…</p></Card>
        ) : alertsQuery.isError ? (
          <Card><Alert kind="error">Unable to load alerts. Try again.</Alert></Card>
        ) : alerts.length === 0 ? (
          <Card>
            <p className="text-sm text-slate-500">
              No alerts yet. Alerts are produced automatically when an alert rule's threshold is crossed.
              Configure rules in the <Link href={`/projects/${projectId}/alerts/rules`} className="text-brand hover:underline">rules page</Link>.
            </p>
          </Card>
        ) : displayed.length === 0 ? (
          <Card><p className="text-sm text-slate-500">No {tab === "active" ? "active" : "resolved"} alerts.</p></Card>
        ) : (
          <div className="flex flex-col gap-4">
            {displayed.map((a) => (
              <Card key={a.id} className="p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <span className={`rounded px-2 py-0.5 text-xs font-semibold ${SEVERITY_COLORS[a.severity] ?? "bg-slate-100 text-slate-700"}`}>
                      {a.severity}
                    </span>
                    <span className={`rounded px-2 py-0.5 text-xs font-semibold ${STATUS_COLORS[a.status] ?? "bg-slate-100 text-slate-700"}`}>
                      {a.status}
                    </span>
                    <span className="text-sm font-medium text-slate-800">{a.message ?? "Alert"}</span>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-slate-500">
                    <span>Occurrences: {a.occurrence_count}</span>
                    <span>Triggered: {new Date(a.triggered_at).toLocaleString()}</span>
                  </div>
                </div>
                {a.observed_value != null ? (
                  <p className="mt-2 text-sm text-slate-600">Observed value: {a.observed_value.toFixed(4)}</p>
                ) : null}
                <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-slate-500">
                  {a.last_seen_at ? <span>Last seen: {new Date(a.last_seen_at).toLocaleString()}</span> : null}
                  {a.resolved_at ? <span>Resolved: {new Date(a.resolved_at).toLocaleString()}</span> : null}
                  <span>
                    Notification:{" "}
                    <span className={a.notification_status === "FAILED" ? "text-red-600" : "text-slate-600"}>
                      {a.notification_status ?? "—"}
                    </span>
                  </span>
                </div>
                {tab === "active" && a.status === "TRIGGERED" ? (
                  <div className="mt-3">
                    <Button variant="secondary" onClick={() => ackMutation.mutate(a.id)} disabled={ackMutation.isPending}>
                      Acknowledge
                    </Button>
                  </div>
                ) : null}
              </Card>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
