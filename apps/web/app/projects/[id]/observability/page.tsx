"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Cell,
  PieChart,
  Pie,
  Legend,
} from "recharts";
import { api } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Alert } from "@/components/ui/Alert";
import { Card } from "@/components/ui/Card";

const TIME_RANGES = [
  { key: "15m", label: "Last 15 minutes", hours: 0.25 },
  { key: "1h", label: "Last hour", hours: 1 },
  { key: "24h", label: "Last 24 hours", hours: 24 },
  { key: "7d", label: "Last 7 days", hours: 24 * 7 },
  { key: "30d", label: "Last 30 days", hours: 24 * 30 },
] as const;

const COLORS = ["#6366f1", "#8b5cf6", "#ec4899", "#f59e0b", "#10b981", "#0ea5e9", "#f43f5e"];

function formatCost(value: number | null | undefined): string {
  if (value === null || value === undefined) return "N/A";
  return `$${value.toFixed(4)}`;
}

function formatMs(value: number | null | undefined): string {
  if (value === null || value === undefined) return "N/A";
  return `${value.toFixed(0)}ms`;
}

function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return "N/A";
  return `${(value * 100).toFixed(1)}%`;
}

export default function ObservabilityDashboardPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const [range, setRange] = useState<(typeof TIME_RANGES)[number]["key"]>("24h");

  const selected = TIME_RANGES.find((r) => r.key === range) ?? TIME_RANGES[2];
  const startTime = new Date(Date.now() - selected.hours * 3600 * 1000).toISOString();
  const endTime = new Date().toISOString();

  const overviewQuery = useQuery({
    queryKey: ["observability-overview", projectId, range],
    queryFn: () =>
      api.getObservabilityOverview(projectId, { start_time: startTime, end_time: endTime }),
  });

  const costQuery = useQuery({
    queryKey: ["observability-cost", projectId, range],
    queryFn: () =>
      api.getObservabilityCost(projectId, { start_time: startTime, end_time: endTime }),
  });

  const latencyQuery = useQuery({
    queryKey: ["observability-latency", projectId, range],
    queryFn: () =>
      api.getObservabilityLatency(projectId, { start_time: startTime, end_time: endTime }),
  });

  const data = overviewQuery.data;
  const hasData = (data?.total_requests ?? 0) > 0;

  // If there is no data, render the empty state (no fake numbers).
  if (overviewQuery.isError || costQuery.isError || latencyQuery.isError) {
    return (
      <AppShell>
        <div className="flex flex-col gap-4">
          <h1 className="text-2xl font-bold text-slate-900">Observability</h1>
          <Alert kind="error">Unable to load observability data. Try again.</Alert>
          <Link href={`/projects/${projectId}/observability`} className="text-sm text-brand hover:underline">
            Try again
          </Link>
        </div>
      </AppShell>
    );
  }

  if (overviewQuery.isLoading || costQuery.isLoading || latencyQuery.isLoading) {
    return (
      <AppShell>
        <div className="flex flex-col gap-4">
          <h1 className="text-2xl font-bold text-slate-900">Observability</h1>
          <Card><p className="text-sm text-slate-400">Loading observability data…</p></Card>
        </div>
      </AppShell>
    );
  }

  const latencyData = [
    { name: "p50", ms: latencyQuery.data?.latency_p50 ?? null },
    { name: "p90", ms: latencyQuery.data?.latency_p90 ?? null },
    { name: "p95", ms: latencyQuery.data?.latency_p95 ?? null },
    { name: "p99", ms: latencyQuery.data?.latency_p99 ?? null },
    { name: "avg", ms: latencyQuery.data?.latency_avg ?? null },
    { name: "max", ms: latencyQuery.data?.latency_max ?? null },
  ].filter((d) => d.ms !== null && d.ms !== undefined);

  const costByModel = (costQuery.data?.cost_by_model ?? []).map((m) => ({
    name: m.model,
    value: m.cost,
  }));

  return (
    <AppShell>
      <div className="flex flex-col gap-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Observability</h1>
            <p className="text-sm text-slate-500">Production AI tracing, metrics, and quality.</p>
          </div>
          <div className="flex items-center gap-4">
            <nav className="flex gap-2 text-sm">
              <Link
                href={`/projects/${projectId}/observability/traces`}
                className="rounded-md border border-slate-200 px-3 py-1.5 text-slate-600 hover:border-brand hover:text-brand"
              >
                Trace Explorer
              </Link>
              <Link
                href={`/projects/${projectId}/alerts`}
                className="rounded-md border border-slate-200 px-3 py-1.5 text-slate-600 hover:border-brand hover:text-brand"
              >
                Alerts
              </Link>
            </nav>
            <select
              aria-label="Time range"
              value={range}
              onChange={(e) => setRange(e.target.value as typeof range)}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            >
              {TIME_RANGES.map((r) => (
                <option key={r.key} value={r.key}>
                  {r.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {!hasData ? (
          <Card>
            <p className="text-sm text-slate-500">
              No observability data yet. Install the AIREX SDK or send events to the ingestion API.
            </p>
          </Card>
        ) : (
          <>
            {/* KPI cards */}
            <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
              <Card className="p-4">
                <span className="text-xs font-semibold uppercase text-slate-500">Requests</span>
                <span className="mt-2 block text-2xl font-bold text-slate-800">{data?.total_requests}</span>
              </Card>
              <Card className="p-4">
                <span className="text-xs font-semibold uppercase text-slate-500">Success Rate</span>
                <span className="mt-2 block text-2xl font-bold text-green-600">{formatPct(data?.success_rate)}</span>
              </Card>
              <Card className="p-4">
                <span className="text-xs font-semibold uppercase text-slate-500">Error Rate</span>
                <span className="mt-2 block text-2xl font-bold text-red-600">{formatPct(data?.error_rate)}</span>
              </Card>
              <Card className="p-4">
                <span className="text-xs font-semibold uppercase text-slate-500">Latency (p95)</span>
                <span className="mt-2 block text-2xl font-bold text-indigo-600">{formatMs(data?.latency_p95)}</span>
              </Card>
              <Card className="p-4">
                <span className="text-xs font-semibold uppercase text-slate-500">Tokens</span>
                <span className="mt-2 block text-2xl font-bold text-slate-800">{data?.total_tokens ?? "N/A"}</span>
              </Card>
              <Card className="p-4">
                <span className="text-xs font-semibold uppercase text-slate-500">Cost</span>
                <span className="mt-2 block text-2xl font-bold text-amber-600">{formatCost(data?.total_cost)}</span>
              </Card>
            </div>

            {/* Latency chart */}
            <Card title="Latency">
              {latencyData.length === 0 ? (
                <p className="text-sm text-slate-500">No latency data in this range.</p>
              ) : (
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={latencyData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" />
                      <YAxis />
                      <Tooltip />
                      <Bar dataKey="ms" name="Latency (ms)" fill="#6366f1" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </Card>

            <div className="grid gap-6 lg:grid-cols-2">
              {/* Cost by model */}
              <Card title="Cost by Model">
                {costByModel.length === 0 ? (
                  <p className="text-sm text-slate-500">No cost data in this range.</p>
                ) : (
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie data={costByModel} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                          {costByModel.map((_, i) => (
                            <Cell key={i} fill={COLORS[i % COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip formatter={(v) => `$${Number(v).toFixed(4)}`} />
                        <Legend />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </Card>

              {/* Model breakdown */}
              <Card title="Model Breakdown">
                {!data?.models?.length ? (
                  <p className="text-sm text-slate-500">No model data in this range.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b text-left text-slate-500">
                          <th className="py-2 pr-4">Model</th>
                          <th className="py-2 pr-4">Requests</th>
                          <th className="py-2 pr-4">Success</th>
                          <th className="py-2 pr-4">Tokens</th>
                          <th className="py-2">Cost</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.models.map((m) => (
                          <tr key={m.model} className="border-b">
                            <td className="py-2 pr-4 font-mono text-slate-900">{m.model}</td>
                            <td className="py-2 pr-4">{m.requests}</td>
                            <td className="py-2 pr-4">{formatPct(m.success_rate)}</td>
                            <td className="py-2 pr-4">{m.tokens}</td>
                            <td className="py-2">{formatCost(m.cost)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Card>
            </div>

            {/* Provider breakdown */}
            <Card title="Provider Breakdown">
              {!data?.providers?.length ? (
                <p className="text-sm text-slate-500">No provider data in this range.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-slate-500">
                        <th className="py-2 pr-4">Provider</th>
                        <th className="py-2 pr-4">Requests</th>
                        <th className="py-2 pr-4">Success</th>
                        <th className="py-2 pr-4">Error</th>
                        <th className="py-2 pr-4">Latency (avg)</th>
                        <th className="py-2 pr-4">Tokens</th>
                        <th className="py-2">Cost</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.providers.map((p) => (
                        <tr key={p.provider} className="border-b">
                          <td className="py-2 pr-4 font-medium text-slate-900">{p.provider}</td>
                          <td className="py-2 pr-4">{p.requests}</td>
                          <td className="py-2 pr-4">{formatPct(p.success_rate)}</td>
                          <td className="py-2 pr-4">{formatPct(p.error_rate)}</td>
                          <td className="py-2 pr-4">{formatMs(p.latency_avg)}</td>
                          <td className="py-2 pr-4">{p.tokens}</td>
                          <td className="py-2">{formatCost(p.cost)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          </>
        )}
      </div>
    </AppShell>
  );
}
