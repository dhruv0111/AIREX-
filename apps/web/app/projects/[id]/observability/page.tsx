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
import { Card, MetricCard } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Select } from "@/components/ui/Input";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/Table";

const TIME_RANGES = [
  { key: "15m", label: "Last 15 minutes", hours: 0.25 },
  { key: "1h", label: "Last hour", hours: 1 },
  { key: "24h", label: "Last 24 hours", hours: 24 },
  { key: "7d", label: "Last 7 days", hours: 24 * 7 },
  { key: "30d", label: "Last 30 days", hours: 24 * 30 },
] as const;

const COLORS = ["#4f46e5", "#06b6d4", "#10b981", "#f59e0b", "#ec4899", "#8b5cf6", "#f43f5e"];

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

  if (overviewQuery.isError || costQuery.isError || latencyQuery.isError) {
    return (
      <AppShell>
        <div className="space-y-4">
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Production Observability</h1>
          <Alert kind="error">Unable to load observability data. Ensure backend ingestion API is reachable.</Alert>
          <Link href={`/projects/${projectId}/observability`}>
            <Button variant="secondary" size="sm">Try again</Button>
          </Link>
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
      <div className="space-y-6" data-testid="observability-view">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 mb-1">
              <Link href={`/projects/${projectId}`} className="hover:text-slate-900 transition">
                ← Back to Project
              </Link>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Production Observability & Tracing
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Live AI telemetry, token consumption, latency percentiles, cost accounting, and span explorer.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Link href={`/projects/${projectId}/observability/traces`}>
              <Button variant="secondary" size="sm" data-testid="trace-explorer-btn">
                Trace Explorer →
              </Button>
            </Link>
            <Select
              aria-label="Time range"
              value={range}
              onChange={(e) => setRange(e.target.value as typeof range)}
              className="w-40"
              data-testid="time-range-select"
            >
              {TIME_RANGES.map((r) => (
                <option key={r.key} value={r.key}>
                  {r.label}
                </option>
              ))}
            </Select>
          </div>
        </div>

        {!hasData && !overviewQuery.isLoading ? (
          <Card className="shadow-sm">
            <div className="p-8 text-center text-slate-500 space-y-3">
              <p className="font-semibold text-slate-800">No telemetry traces recorded in this window</p>
              <p className="text-xs text-slate-400 max-w-md mx-auto">
                Invoke models via the test console or integrate the AIREX SDK to monitor real-time requests.
              </p>
              <Link href={`/projects/${projectId}/models`}>
                <Button size="sm">Open Model Test Console →</Button>
              </Link>
            </div>
          </Card>
        ) : (
          <>
            {/* KPI Metric Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4" data-testid="obs-kpi-grid">
              <MetricCard
                label="Total Requests"
                value={data?.total_requests ?? 0}
                accent="brand"
              />
              <MetricCard
                label="Success Rate"
                value={formatPct(data?.success_rate)}
                accent="success"
              />
              <MetricCard
                label="Error Rate"
                value={formatPct(data?.error_rate)}
                accent={Number(data?.error_rate ?? 0) > 0 ? "danger" : "neutral"}
              />
              <MetricCard
                label="p95 Latency"
                value={formatMs(data?.latency_p95)}
                accent="brand"
              />
              <MetricCard
                label="Token Usage"
                value={data?.total_tokens ?? 0}
                accent="neutral"
              />
              <MetricCard
                label="Inference Cost"
                value={formatCost(data?.total_cost)}
                accent="warning"
              />
            </div>

            {/* Latency Percentiles Bar Chart */}
            <Card title="Latency Distribution (ms)" subtitle="Percentile distribution across active model invocations" className="shadow-sm">
              {latencyData.length === 0 ? (
                <p className="text-xs text-slate-400 py-6 text-center">No latency distribution data in this time range.</p>
              ) : (
                <div className="h-64 w-full pt-4">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={latencyData}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                      <XAxis dataKey="name" tick={{ fill: "#64748b", fontSize: 12 }} />
                      <YAxis tick={{ fill: "#64748b", fontSize: 12 }} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#ffffff",
                          border: "1px solid #e2e8f0",
                          borderRadius: "0.5rem",
                          boxShadow: "0 4px 6px -1px rgba(0,0,0,0.1)",
                        }}
                      />
                      <Bar dataKey="ms" name="Latency (ms)" fill="#4f46e5" radius={[6, 6, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </Card>

            {/* Model & Provider Breakdown Grid */}
            <div className="grid gap-6 lg:grid-cols-2">
              {/* Cost by Model */}
              <Card title="Cost Allocation by Model" subtitle="Cost distribution across models" className="shadow-sm">
                {costByModel.length === 0 ? (
                  <p className="text-xs text-slate-400 py-6 text-center">No model cost data recorded.</p>
                ) : (
                  <div className="h-64 w-full">
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

              {/* Model Breakdown Table */}
              <Card title="Model Performance Breakdown" subtitle="Detailed per-model traffic and quality breakdown" className="shadow-sm">
                {!data?.models?.length ? (
                  <p className="text-xs text-slate-400 py-6 text-center">No model metrics in this range.</p>
                ) : (
                  <Table>
                    <TableHeader>
                      <tr>
                        <TableHead>Model</TableHead>
                        <TableHead>Requests</TableHead>
                        <TableHead>Success Rate</TableHead>
                        <TableHead>Tokens</TableHead>
                        <TableHead>Cost</TableHead>
                      </tr>
                    </TableHeader>
                    <TableBody>
                      {data.models.map((m) => (
                        <TableRow key={m.model}>
                          <TableCell className="font-mono text-xs font-semibold text-slate-800">{m.model}</TableCell>
                          <TableCell className="font-mono text-xs text-slate-600">{m.requests}</TableCell>
                          <TableCell className="font-mono text-xs text-emerald-700 font-semibold">{formatPct(m.success_rate)}</TableCell>
                          <TableCell className="font-mono text-xs text-slate-600">{m.tokens}</TableCell>
                          <TableCell className="font-mono text-xs text-slate-900 font-bold">{formatCost(m.cost)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </Card>
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
}
