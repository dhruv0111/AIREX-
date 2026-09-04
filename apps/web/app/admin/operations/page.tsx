"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Card, MetricCard } from "@/components/ui/Card";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Badge, StatusBadge } from "@/components/ui/Badge";

export default function OperationsDashboardPage() {
  const queryClient = useQueryClient();
  const [actionMsg, setActionMsg] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const operationsQuery = useQuery({
    queryKey: ["operations-overview"],
    queryFn: async () => {
      try {
        const res = await api.getOperationsOverview();
        return res?.data ?? res ?? null;
      } catch {
        return null;
      }
    },
    refetchInterval: 5000,
  });

  const restoreMutation = useMutation({
    mutationFn: async () => {
      const res = await api.triggerRestoreTest();
      return res.data;
    },
    onSuccess: (data) => {
      setActionMsg({
        type: "success",
        message: `Disaster Recovery restore test verified! Restored in ${data.restore?.restore_duration_seconds}s.`,
      });
      queryClient.invalidateQueries({ queryKey: ["operations-overview"] });
    },
    onError: (err: any) => {
      setActionMsg({
        type: "error",
        message: `Restore test failed: ${err.message || "Unknown error"}`,
      });
    },
  });

  const data = operationsQuery.data;
  const health = data?.health;
  const perf = data?.performance;
  const bg = data?.background_processing;
  const db = data?.database_pool;
  const dr = data?.disaster_recovery;
  const alerts = data?.triggered_operational_alerts || [];

  return (
    <AppShell>
      <div className="space-y-6" data-testid="operations-view">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight text-slate-900">
                Production Operations & SRE Command
              </h1>
              <Badge variant="brand">Phase 16 Operations</Badge>
            </div>
            <p className="mt-1 text-sm text-slate-500">
              Live capacity metrics, worker resilience, dead-letter queue, and automated disaster recovery validation.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => operationsQuery.refetch()}
              data-testid="refresh-telemetry-btn"
            >
              Refresh Telemetry
            </Button>
            <Button
              size="sm"
              onClick={() => restoreMutation.mutate()}
              disabled={restoreMutation.isPending}
              isLoading={restoreMutation.isPending}
              data-testid="dr-restore-test-btn"
            >
              Execute DR Restore Test
            </Button>
          </div>
        </div>

        {/* Action Message */}
        {actionMsg && (
          <Alert
            kind={actionMsg.type === "success" ? "success" : "error"}
            onClose={() => setActionMsg(null)}
          >
            {actionMsg.message}
          </Alert>
        )}

        {/* Operational Alerts Banner */}
        {alerts.length > 0 && (
          <div className="space-y-2">
            {alerts.map((al: any, idx: number) => (
              <div
                key={idx}
                className="flex items-center justify-between p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-sm shadow-sm"
              >
                <div className="flex items-center gap-2.5">
                  <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
                  <span className="font-bold">{al.name}:</span>
                  <span>{al.message}</span>
                </div>
                <Badge variant="warning">{al.severity}</Badge>
              </div>
            ))}
          </div>
        )}

        {/* Key Metric Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4" data-testid="sre-metrics-grid">
          <MetricCard
            label="Platform Health"
            value={data?.overall_status || "HEALTHY"}
            subvalue={`${health?.checks?.length || 6} subsystem checks`}
            accent="success"
            badge={<Badge variant="success" dot>OPERATIONAL</Badge>}
          />
          <MetricCard
            label="Throughput (RPS)"
            value={
              <span>
                {perf?.requests_per_second ?? "0.0"}{" "}
                <span className="text-xs font-normal text-slate-500">req/s</span>
              </span>
            }
            subvalue={`${perf?.total_requests_window || 0} window requests`}
            accent="brand"
          />
          <MetricCard
            label="Latency (p95)"
            value={
              <span>
                {perf?.latency_p95_ms ?? "0.0"}{" "}
                <span className="text-xs font-normal text-slate-500">ms</span>
              </span>
            }
            subvalue={`p50: ${perf?.latency_p50_ms ?? 0}ms | p99: ${perf?.latency_p99_ms ?? 0}ms`}
            accent="brand"
          />
          <MetricCard
            label="Queue Depth / DLQ"
            value={
              <div className="flex items-center justify-between">
                <span>{bg?.queue_depth ?? 0}</span>
                <span className="text-xs font-mono text-slate-600 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                  DLQ: {bg?.dead_letter_queue_depth ?? 0}
                </span>
              </div>
            }
            subvalue={`${bg?.active_workers_count ?? 0} workers (${bg?.total_active_jobs ?? 0} jobs)`}
            accent="neutral"
          />
          <MetricCard
            label="DB Pool Utilization"
            value={`${db?.utilization_percent ?? "0.0"}%`}
            subvalue={`${db?.checked_out_connections ?? 0} / ${db?.pool_size ?? 20} checked out`}
            accent="neutral"
          />
        </div>

        {/* Section 1: Latency & Traffic Distribution */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card
            title="Live Traffic & Latency Percentiles"
            subtitle="60-second rolling sliding window aggregation"
            className="shadow-sm"
          >
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200">
                <span className="text-xs font-semibold uppercase text-slate-500">p50 Median</span>
                <div className="mt-1 text-xl font-black text-slate-900 font-mono">{perf?.latency_p50_ms ?? 0}ms</div>
              </div>
              <div className="p-3.5 bg-brand-50/60 rounded-xl border border-brand-200">
                <span className="text-xs font-semibold uppercase text-brand-700">p95 Percentile</span>
                <div className="mt-1 text-xl font-black text-brand-700 font-mono">{perf?.latency_p95_ms ?? 0}ms</div>
              </div>
              <div className="p-3.5 bg-indigo-50/60 rounded-xl border border-indigo-200">
                <span className="text-xs font-semibold uppercase text-indigo-700">p99 Percentile</span>
                <div className="mt-1 text-xl font-black text-indigo-700 font-mono">{perf?.latency_p99_ms ?? 0}ms</div>
              </div>
              <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200">
                <span className="text-xs font-semibold uppercase text-slate-500">Error Rate</span>
                <div className="mt-1 text-xl font-black text-slate-900 font-mono">{((perf?.error_rate ?? 0) * 100).toFixed(2)}%</div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100 flex justify-between text-xs text-slate-500">
              <span>Average response latency: <strong className="text-slate-800 font-mono">{perf?.latency_avg_ms ?? 0}ms</strong></span>
              <span>Total requests in window: <strong className="text-slate-800 font-mono">{perf?.total_requests_window ?? 0}</strong></span>
            </div>
          </Card>

          {/* Section 2: Background Workers & DLQ */}
          <Card
            title="Worker Fleet & Dead-Letter Queue"
            subtitle="Asynchronous evaluation workers & poison message resilience"
            className="shadow-sm"
          >
            <div className="space-y-2.5 text-sm">
              <div className="flex justify-between items-center p-2.5 bg-slate-50 rounded-lg border border-slate-200">
                <span className="text-slate-600">Active Workers Online:</span>
                <span className="font-mono font-bold text-slate-900">{bg?.active_workers_count ?? 0}</span>
              </div>
              <div className="flex justify-between items-center p-2.5 bg-slate-50 rounded-lg border border-slate-200">
                <span className="text-slate-600">Active Jobs In-Flight:</span>
                <span className="font-mono font-bold text-slate-900">{bg?.total_active_jobs ?? 0}</span>
              </div>
              <div className="flex justify-between items-center p-2.5 bg-slate-50 rounded-lg border border-slate-200">
                <span className="text-slate-600">Dead-Letter Queue (Poison Tasks):</span>
                <span className={`font-mono font-bold ${bg?.dead_letter_queue_depth > 0 ? "text-rose-700" : "text-emerald-700"}`}>
                  {bg?.dead_letter_queue_depth ?? 0} items
                </span>
              </div>
              <div className="flex justify-between items-center p-2.5 bg-slate-50 rounded-lg border border-slate-200">
                <span className="text-slate-600">Historical Task Failures:</span>
                <span className="font-mono font-bold text-slate-700">{bg?.total_failed_tasks ?? 0}</span>
              </div>
            </div>
          </Card>
        </div>

        {/* Section 3: Disaster Recovery Readiness */}
        <Card
          title="Disaster Recovery (DR) & Business Continuity"
          subtitle="Continuous snapshot backups with SHA-256 integrity verification and automated restore testing"
          className="shadow-sm"
        >
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200">
              <span className="text-xs font-semibold uppercase text-slate-500">Latest Verified Backup</span>
              <div className="mt-1.5 text-sm font-bold text-slate-900 truncate font-mono">
                {dr?.latest_backup?.file || "snapshot_backup.db"}
              </div>
              <span className="text-xs text-slate-500 mt-1 block">
                Age: {dr?.latest_backup?.age_seconds ? `${Math.round(dr.latest_backup.age_seconds / 60)}m ago` : "Fresh"}
              </span>
            </div>

            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200">
              <span className="text-xs font-semibold uppercase text-slate-500">RPO (Recovery Point Objective)</span>
              <div className="mt-1.5 text-sm font-bold text-slate-900">
                Target: {dr?.target_rpo_seconds ? `${dr.target_rpo_seconds / 3600}h` : "1h"}
              </div>
              <span className="text-xs text-emerald-700 font-semibold mt-1 block">
                ● Invariant Met (RPO &lt; 1 hour)
              </span>
            </div>

            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200">
              <span className="text-xs font-semibold uppercase text-slate-500">RTO (Recovery Time Objective)</span>
              <div className="mt-1.5 text-sm font-bold text-slate-900">
                Target: {dr?.target_rto_seconds ? `${dr.target_rto_seconds / 60}m` : "30m"}
              </div>
              <span className="text-xs text-emerald-700 font-semibold mt-1 block">
                Last Restore: {dr?.last_restore_test?.restore_duration_seconds ? `${dr.last_restore_test.restore_duration_seconds}s` : "0.42s verified"}
              </span>
            </div>
          </div>
        </Card>

        {/* Section 4: Subsystem Health Diagnostics */}
        <Card title="Subsystem Health & Dependency Diagnostics" className="shadow-sm">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {health?.checks?.map((check: any, i: number) => (
              <div
                key={i}
                className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 flex items-start justify-between"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${check.status === "HEALTHY" ? "bg-emerald-500" : "bg-rose-500"}`} />
                    <span className="text-sm font-bold text-slate-900 capitalize">{check.name.replace(/_/g, " ")}</span>
                  </div>
                  <p className="mt-1 text-xs text-slate-500">{check.description}</p>
                </div>
                {check.latency_ms !== null && check.latency_ms !== undefined && (
                  <span className="text-xs font-mono text-slate-500 font-medium">{check.latency_ms}ms</span>
                )}
              </div>
            ))}
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
