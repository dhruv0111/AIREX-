"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Alert } from "@/components/ui/Alert";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

const TIME_RANGES = [
  { key: "1h", label: "Last hour", hours: 1 },
  { key: "24h", label: "Last 24 hours", hours: 24 },
  { key: "7d", label: "Last 7 days", hours: 24 * 7 },
  { key: "30d", label: "Last 30 days", hours: 24 * 30 },
] as const;

const PAGE_SIZE = 20;

const STATUS_COLORS: Record<string, string> = {
  SUCCESS: "bg-green-100 text-green-800",
  ERROR: "bg-red-100 text-red-800",
  TIMEOUT: "bg-amber-100 text-amber-800",
  CANCELLED: "bg-slate-100 text-slate-700",
  RATE_LIMITED: "bg-orange-100 text-orange-800",
};

function statusBadge(status: string | null) {
  if (!status) return <span className="text-slate-400">—</span>;
  const cls = STATUS_COLORS[status] ?? "bg-slate-100 text-slate-700";
  return <span className={`rounded px-2 py-0.5 text-xs font-semibold ${cls}`}>{status}</span>;
}

export default function TraceExplorerPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const [range, setRange] = useState<(typeof TIME_RANGES)[number]["key"]>("24h");
  const [status, setStatus] = useState("");
  const [traceId, setTraceId] = useState("");
  const [provider, setProvider] = useState("");
  const [offset, setOffset] = useState(0);

  const selected = TIME_RANGES.find((r) => r.key === range) ?? TIME_RANGES[1];
  const startTime = new Date(Date.now() - selected.hours * 3600 * 1000).toISOString();
  const endTime = new Date().toISOString();

  const query = useQuery({
    queryKey: ["observability-traces", projectId, range, status, traceId, provider, offset],
    queryFn: () =>
      api.listTraces(projectId, {
        start_time: startTime,
        end_time: endTime,
        status: status || undefined,
        trace_id: traceId || undefined,
        provider: provider || undefined,
        limit: PAGE_SIZE,
        offset,
      }),
  });

  const traces = query.data?.traces ?? [];
  const total = query.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <AppShell>
      <div className="flex flex-col gap-6">
        <div>
          <Link href={`/projects/${projectId}/observability`} className="text-sm text-brand hover:underline">
            ← Observability
          </Link>
          <h1 className="mt-2 text-2xl font-bold text-slate-900">Trace Explorer</h1>
          <p className="text-sm text-slate-500">Search and inspect production AI traces.</p>
        </div>

        {/* Filters */}
        <Card>
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-500">Time range</label>
              <select
                aria-label="Time range"
                value={range}
                onChange={(e) => {
                  setRange(e.target.value as typeof range);
                  setOffset(0);
                }}
                className="mt-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm"
              >
                {TIME_RANGES.map((r) => (
                  <option key={r.key} value={r.key}>{r.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-500">Status</label>
              <select
                aria-label="Status"
                value={status}
                onChange={(e) => { setStatus(e.target.value); setOffset(0); }}
                className="mt-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm"
              >
                <option value="">All</option>
                <option value="SUCCESS">SUCCESS</option>
                <option value="ERROR">ERROR</option>
                <option value="TIMEOUT">TIMEOUT</option>
                <option value="CANCELLED">CANCELLED</option>
                <option value="RATE_LIMITED">RATE_LIMITED</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-500">Provider</label>
              <input
                aria-label="Provider"
                value={provider}
                onChange={(e) => { setProvider(e.target.value); setOffset(0); }}
                placeholder="e.g. openai"
                className="mt-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-500">Trace ID</label>
              <input
                aria-label="Trace ID"
                value={traceId}
                onChange={(e) => { setTraceId(e.target.value); setOffset(0); }}
                placeholder="trace_…"
                className="mt-1 rounded-md border border-slate-300 px-3 py-1.5 font-mono text-sm"
              />
            </div>
          </div>
        </Card>

        {query.isLoading ? (
          <Card><p className="text-sm text-slate-400">Loading traces…</p></Card>
        ) : query.isError ? (
          <Card><Alert kind="error">Unable to load observability data. Try again.</Alert></Card>
        ) : traces.length === 0 ? (
          <Card>
            <p className="text-sm text-slate-500">
              No observability data yet. Install the AIREX SDK or send events to the ingestion API.
            </p>
          </Card>
        ) : (
          <Card>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-slate-500">
                    <th className="py-2 pr-4">Trace ID</th>
                    <th className="py-2 pr-4">Operation</th>
                    <th className="py-2 pr-4">Service</th>
                    <th className="py-2 pr-4">Environment</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2 pr-4">Duration</th>
                    <th className="py-2 pr-4">Quality</th>
                    <th className="py-2">Started</th>
                  </tr>
                </thead>
                <tbody>
                  {traces.map((t) => (
                    <tr key={t.id} className="border-b hover:bg-slate-50">
                      <td className="py-3 pr-4">
                        <Link
                          href={`/projects/${projectId}/observability/traces/${t.trace_id}`}
                          className="font-mono text-brand hover:underline"
                        >
                          {t.trace_id}
                        </Link>
                      </td>
                      <td className="py-3 pr-4 text-slate-800">{t.operation_name ?? "—"}</td>
                      <td className="py-3 pr-4 text-slate-600">{t.service_name ?? "—"}</td>
                      <td className="py-3 pr-4 text-slate-600">{t.environment}</td>
                      <td className="py-3 pr-4">{statusBadge(t.status)}</td>
                      <td className="py-3 pr-4 text-slate-600">
                        {t.duration_ms != null ? `${t.duration_ms.toFixed(0)}ms` : "—"}
                      </td>
                      <td className="py-3 pr-4 text-slate-600">
                        {t.quality_score != null ? t.quality_score.toFixed(2) : "—"}
                      </td>
                      <td className="py-3 text-slate-500">{new Date(t.start_time).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {totalPages > 1 ? (
              <div className="mt-4 flex items-center justify-between border-t pt-4">
                <Button variant="secondary" onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))} disabled={offset === 0}>
                  Previous
                </Button>
                <span className="text-xs text-slate-500">
                  Page {Math.floor(offset / PAGE_SIZE) + 1} of {totalPages} · {total} traces
                </span>
                <Button variant="secondary" onClick={() => setOffset((o) => o + PAGE_SIZE)} disabled={offset + PAGE_SIZE >= total}>
                  Next
                </Button>
              </div>
            ) : null}
          </Card>
        )}
      </div>
    </AppShell>
  );
}
