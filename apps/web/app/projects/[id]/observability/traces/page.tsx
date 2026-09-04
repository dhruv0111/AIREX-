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
import { StatusBadge, Badge } from "@/components/ui/Badge";
import { Input, Select } from "@/components/ui/Input";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/Table";

const TIME_RANGES = [
  { key: "1h", label: "Last hour", hours: 1 },
  { key: "24h", label: "Last 24 hours", hours: 24 },
  { key: "7d", label: "Last 7 days", hours: 24 * 7 },
  { key: "30d", label: "Last 30 days", hours: 24 * 30 },
] as const;

const PAGE_SIZE = 20;

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
      <div className="space-y-6" data-testid="trace-explorer-view">
        {/* Header */}
        <div className="border-b border-slate-200 pb-5">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 mb-1">
            <Link href={`/projects/${projectId}/observability`} className="hover:text-slate-900 transition">
              ← Back to Observability
            </Link>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Distributed Trace Explorer
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Inspect individual LLM spans, token latencies, error stacks, and execution steps.
          </p>
        </div>

        {/* Filter Toolbar */}
        <Card className="shadow-sm">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">Time Range</label>
              <Select
                aria-label="Time range"
                value={range}
                onChange={(e) => {
                  setRange(e.target.value as typeof range);
                  setOffset(0);
                }}
              >
                {TIME_RANGES.map((r) => (
                  <option key={r.key} value={r.key}>{r.label}</option>
                ))}
              </Select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">Execution Status</label>
              <Select
                aria-label="Status"
                value={status}
                onChange={(e) => { setStatus(e.target.value); setOffset(0); }}
              >
                <option value="">All Statuses</option>
                <option value="SUCCESS">SUCCESS</option>
                <option value="ERROR">ERROR</option>
                <option value="TIMEOUT">TIMEOUT</option>
                <option value="CANCELLED">CANCELLED</option>
                <option value="RATE_LIMITED">RATE_LIMITED</option>
              </Select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">Provider Filter</label>
              <Input
                aria-label="Provider"
                value={provider}
                onChange={(e) => { setProvider(e.target.value); setOffset(0); }}
                placeholder="e.g. openai, local"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">Trace ID</label>
              <Input
                aria-label="Trace ID"
                value={traceId}
                onChange={(e) => { setTraceId(e.target.value); setOffset(0); }}
                placeholder="trace_…"
                className="font-mono text-xs"
              />
            </div>
          </div>
        </Card>

        {query.isLoading ? (
          <div className="p-8 text-center text-slate-400">Loading traces…</div>
        ) : query.isError ? (
          <Alert kind="error">Unable to load observability traces. Check API connection.</Alert>
        ) : traces.length === 0 ? (
          <Card className="shadow-sm">
            <p className="text-sm text-slate-500 py-8 text-center">
              No traces recorded yet for this project and time window.
            </p>
          </Card>
        ) : (
          <Card title={`Recorded Traces (${total})`} className="shadow-sm">
            <Table>
              <TableHeader>
                <tr>
                  <TableHead>Trace ID</TableHead>
                  <TableHead>Operation</TableHead>
                  <TableHead>Service</TableHead>
                  <TableHead>Environment</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Quality Score</TableHead>
                  <TableHead className="text-right">Timestamp</TableHead>
                </tr>
              </TableHeader>
              <TableBody>
                {traces.map((t) => (
                  <TableRow key={t.id}>
                    <TableCell className="font-mono text-xs font-semibold">
                      <span className="text-brand-600 hover:underline cursor-pointer">
                        {t.trace_id.slice(0, 16)}…
                      </span>
                    </TableCell>
                    <TableCell className="font-semibold text-slate-800 text-xs">{t.operation_name ?? "—"}</TableCell>
                    <TableCell className="text-slate-600 text-xs">{t.service_name ?? "—"}</TableCell>
                    <TableCell>
                      <Badge variant="neutral">{t.environment}</Badge>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={t.status} />
                    </TableCell>
                    <TableCell className="font-mono text-xs text-slate-600">
                      {t.duration_ms != null ? `${t.duration_ms.toFixed(0)}ms` : "—"}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-slate-800">
                      {t.quality_score != null ? t.quality_score.toFixed(2) : "—"}
                    </TableCell>
                    <TableCell className="text-xs text-slate-500 font-mono text-right">
                      {new Date(t.start_time).toLocaleString()}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            {totalPages > 1 && (
              <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-4 text-xs">
                <Button variant="secondary" size="sm" onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))} disabled={offset === 0}>
                  Previous
                </Button>
                <span className="text-slate-500">
                  Page {Math.floor(offset / PAGE_SIZE) + 1} of {totalPages} ({total} traces)
                </span>
                <Button variant="secondary" size="sm" onClick={() => setOffset((o) => o + PAGE_SIZE)} disabled={offset + PAGE_SIZE >= total}>
                  Next
                </Button>
              </div>
            )}
          </Card>
        )}
      </div>
    </AppShell>
  );
}
