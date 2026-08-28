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

const METRICS = [
  "error_rate",
  "latency_p95",
  "cost",
  "token_usage",
  "request_rate",
  "quality_score",
] as const;
const OPERATORS = [">", "<", ">=", "<=", "=="] as const;
const SEVERITIES = ["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"] as const;

const SEVERITY_COLORS: Record<string, string> = {
  INFO: "bg-sky-100 text-sky-800",
  LOW: "bg-emerald-100 text-emerald-800",
  MEDIUM: "bg-amber-100 text-amber-800",
  HIGH: "bg-orange-100 text-orange-800",
  CRITICAL: "bg-red-100 text-red-800",
};

export default function AlertRulesPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [metric, setMetric] = useState<string>("error_rate");
  const [operator, setOperator] = useState<string>(">");
  const [threshold, setThreshold] = useState("0.05");
  const [duration, setDuration] = useState("600");
  const [cooldown, setCooldown] = useState("3600");
  const [severity, setSeverity] = useState("MEDIUM");
  const [environment, setEnvironment] = useState("");

  const rulesQuery = useQuery({
    queryKey: ["alert-rules", projectId],
    queryFn: () => api.listAlertRules(projectId),
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["alert-rules", projectId] });

  const createMutation = useMutation({
    mutationFn: () =>
      api.createAlertRule(projectId, {
        name,
        metric,
        operator,
        threshold: parseFloat(threshold),
        duration_seconds: parseInt(duration, 10),
        cooldown_seconds: parseInt(cooldown, 10),
        severity,
        environment: environment || undefined,
      }),
    onSuccess: () => {
      setError(null);
      setName("");
      setThreshold("0.05");
      refresh();
    },
    onError: (e) => setError(e instanceof ApiClientError ? e.message : "Failed to create rule"),
  });

  const toggleMutation = useMutation({
    mutationFn: (rule: { id: string; is_enabled: boolean }) =>
      api.updateAlertRule(rule.id, { is_enabled: !rule.is_enabled }),
    onSuccess: refresh,
    onError: (e) => setError(e instanceof ApiClientError ? e.message : "Failed to update rule"),
  });

  const deleteMutation = useMutation({
    mutationFn: (ruleId: string) => api.deleteAlertRule(ruleId),
    onSuccess: refresh,
    onError: (e) => setError(e instanceof ApiClientError ? e.message : "Failed to delete rule"),
  });

  const rules = rulesQuery.data ?? [];

  return (
    <AppShell>
      <div className="flex flex-col gap-6">
        <div>
          <Link href={`/projects/${projectId}/alerts`} className="text-sm text-brand hover:underline">
            ← Alerts
          </Link>
          <h1 className="mt-2 text-2xl font-bold text-slate-900">Alert Rules</h1>
          <p className="text-sm text-slate-500">Configure threshold-based production alert rules.</p>
        </div>

        {error ? <Alert kind="error">{error}</Alert> : null}

        <Card title="Create rule">
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
            <input
              aria-label="Rule name"
              placeholder="Rule name (e.g. High error rate)"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
            <select
              aria-label="Metric"
              value={metric}
              onChange={(e) => setMetric(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              {METRICS.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
            <div className="flex items-center gap-2">
              <select
                aria-label="Operator"
                value={operator}
                onChange={(e) => setOperator(e.target.value)}
                className="rounded-md border border-slate-300 px-3 py-2 text-sm"
              >
                {OPERATORS.map((o) => (
                  <option key={o} value={o}>{o}</option>
                ))}
              </select>
              <input
                aria-label="Threshold"
                type="number"
                step="any"
                value={threshold}
                onChange={(e) => setThreshold(e.target.value)}
                className="w-28 rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <select
              aria-label="Severity"
              value={severity}
              onChange={(e) => setSeverity(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              {SEVERITIES.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            <input
              aria-label="Window seconds"
              type="number"
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
              placeholder="Window (s)"
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
            <input
              aria-label="Cooldown seconds"
              type="number"
              value={cooldown}
              onChange={(e) => setCooldown(e.target.value)}
              placeholder="Cooldown (s)"
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
            <input
              aria-label="Environment"
              value={environment}
              onChange={(e) => setEnvironment(e.target.value)}
              placeholder="Environment (optional)"
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
            <Button onClick={() => createMutation.mutate()} disabled={createMutation.isPending || !name}>
              Create rule
            </Button>
          </div>
        </Card>

        {rulesQuery.isLoading ? (
          <Card><p className="text-sm text-slate-400">Loading rules…</p></Card>
        ) : rulesQuery.isError ? (
          <Card><Alert kind="error">Unable to load alert rules. Try again.</Alert></Card>
        ) : rules.length === 0 ? (
          <Card><p className="text-sm text-slate-500">No alert rules yet. Create one above.</p></Card>
        ) : (
          <Card>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-slate-500">
                    <th className="py-2 pr-4">Name</th>
                    <th className="py-2 pr-4">Condition</th>
                    <th className="py-2 pr-4">Severity</th>
                    <th className="py-2 pr-4">Window</th>
                    <th className="py-2 pr-4">Environment</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {rules.map((r) => (
                    <tr key={r.id} className="border-b">
                      <td className="py-2 pr-4 font-medium text-slate-900">{r.name}</td>
                      <td className="py-2 pr-4 font-mono text-slate-700">
                        {r.metric} {r.operator} {r.threshold}
                      </td>
                      <td className="py-2 pr-4">
                        <span className={`rounded px-2 py-0.5 text-xs font-semibold ${SEVERITY_COLORS[r.severity] ?? "bg-slate-100 text-slate-700"}`}>
                          {r.severity}
                        </span>
                      </td>
                      <td className="py-2 pr-4 text-slate-600">{r.duration_seconds}s</td>
                      <td className="py-2 pr-4 text-slate-600">{r.environment ?? "all"}</td>
                      <td className="py-2 pr-4">
                        <span className={`rounded px-2 py-0.5 text-xs font-semibold ${r.is_enabled ? "bg-green-100 text-green-800" : "bg-slate-100 text-slate-600"}`}>
                          {r.is_enabled ? "ENABLED" : "DISABLED"}
                        </span>
                      </td>
                      <td className="py-2">
                        <div className="flex gap-2">
                          <Button variant="secondary" onClick={() => toggleMutation.mutate(r)}>
                            {r.is_enabled ? "Disable" : "Enable"}
                          </Button>
                          <Button
                            variant="danger"
                            onClick={() => {
                              if (confirm(`Delete alert rule "${r.name}"?`)) deleteMutation.mutate(r.id);
                            }}
                          >
                            Delete
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
