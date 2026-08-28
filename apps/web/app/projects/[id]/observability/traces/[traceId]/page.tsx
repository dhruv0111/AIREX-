"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api, ApiClientError } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Alert } from "@/components/ui/Alert";
import { Card } from "@/components/ui/Card";

function formatCost(value: number | null | undefined): string {
  if (value === null || value === undefined) return "N/A";
  return `$${value.toFixed(4)}`;
}

const SPAN_TYPE_COLORS: Record<string, string> = {
  LLM: "bg-indigo-100 text-indigo-800",
  RETRIEVAL: "bg-sky-100 text-sky-800",
  TOOL: "bg-amber-100 text-amber-800",
  PROMPT: "bg-violet-100 text-violet-800",
  EVALUATION: "bg-emerald-100 text-emerald-800",
  CUSTOM: "bg-slate-100 text-slate-700",
};

interface SpanNode {
  span: {
    span_id: string;
    parent_span_id: string | null;
    name: string;
    span_type: string;
    status: string;
    duration_ms: number | null;
    provider: string | null;
    model: string | null;
    input_tokens: number | null;
    output_tokens: number | null;
    total_tokens: number | null;
    estimated_cost: number | null;
    error_category: string | null;
    error: string | null;
    start_time: string;
  };
  children: SpanNode[];
}

function buildTree(spans: SpanNode["span"][]): SpanNode[] {
  const nodes = new Map<string, SpanNode>();
  const roots: SpanNode[] = [];
  spans.forEach((s) => nodes.set(s.span_id, { span: s, children: [] }));
  spans.forEach((s) => {
    const node = nodes.get(s.span_id)!;
    if (s.parent_span_id && nodes.has(s.parent_span_id)) {
      nodes.get(s.parent_span_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  });
  return roots;
}

function SpanRow({ node, depth }: { node: SpanNode; depth: number }) {
  const s = node.span;
  const badge = SPAN_TYPE_COLORS[s.span_type] ?? SPAN_TYPE_COLORS.CUSTOM;
  return (
    <>
      <div
        className="flex flex-wrap items-center gap-2 border-b py-2 text-sm"
        style={{ paddingLeft: `${depth * 24 + 12}px` }}
      >
        <span className={`rounded px-2 py-0.5 text-xs font-semibold ${badge}`}>{s.span_type}</span>
        <span className="font-medium text-slate-800">{s.name}</span>
        {s.status === "ERROR" ? (
          <span className="rounded bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-800">ERROR</span>
        ) : null}
        {s.model ? <span className="font-mono text-xs text-slate-500">{s.model}</span> : null}
        <span className="text-xs text-slate-500">{s.duration_ms != null ? `${s.duration_ms.toFixed(0)}ms` : "—"}</span>
        <span className="text-xs text-slate-500">
          {s.total_tokens != null ? `${s.total_tokens} tokens` : ""}
        </span>
        <span className="text-xs text-amber-600">{formatCost(s.estimated_cost)}</span>
      </div>
      {s.error ? <p className="text-xs text-red-600" style={{ paddingLeft: `${depth * 24 + 12}px` }}>{s.error}</p> : null}
      {node.children.map((c) => (
        <SpanRow key={c.span.span_id} node={c} depth={depth + 1} />
      ))}
    </>
  );
}

export default function TraceDetailPage() {
  const params = useParams<{ id: string; traceId: string }>();
  const projectId = params.id;
  const traceId = params.traceId;

  const query = useQuery({
    queryKey: ["observability-trace", traceId],
    queryFn: () => api.getTraceDetail(traceId),
    retry: false,
  });

  if (query.isLoading) {
    return (
      <AppShell>
        <Card><p className="text-sm text-slate-400">Loading trace…</p></Card>
      </AppShell>
    );
  }

  if (query.isError) {
    const status = query.error instanceof ApiClientError ? query.error.status : 0;
    return (
      <AppShell>
        <Card>
          <Alert kind="error">
            {status === 404 ? "Trace not found." : "Unable to load observability data. Try again."}
          </Alert>
          <Link href={`/projects/${projectId}/observability/traces`} className="mt-4 inline-block text-sm text-brand hover:underline">
            ← Back to trace explorer
          </Link>
        </Card>
      </AppShell>
    );
  }

  const trace = query.data!.trace;
  const spans = query.data!.spans;
  const tree = buildTree(spans);

  const llmSpans = spans.filter((s) => s.span_type === "LLM");
  const totalCost = llmSpans.reduce((sum, s) => sum + (s.estimated_cost ?? 0), 0);
  const totalTokens = llmSpans.reduce((sum, s) => sum + (s.total_tokens ?? 0), 0);

  return (
    <AppShell>
      <div className="flex flex-col gap-6">
        <div>
          <Link href={`/projects/${projectId}/observability/traces`} className="text-sm text-brand hover:underline">
            ← Trace explorer
          </Link>
          <h1 className="mt-2 break-all text-2xl font-bold text-slate-900">{trace.trace_id}</h1>
          <p className="text-sm text-slate-500">
            {trace.operation_name ?? "—"} · {trace.service_name ?? "unknown service"} · {trace.environment}
          </p>
        </div>

        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <Card className="p-4">
            <span className="text-xs font-semibold uppercase text-slate-500">Status</span>
            <span className="mt-2 block text-xl font-bold text-slate-800">{trace.status ?? "—"}</span>
          </Card>
          <Card className="p-4">
            <span className="text-xs font-semibold uppercase text-slate-500">Duration</span>
            <span className="mt-2 block text-xl font-bold text-indigo-600">
              {trace.duration_ms != null ? `${trace.duration_ms.toFixed(0)}ms` : "N/A"}
            </span>
          </Card>
          <Card className="p-4">
            <span className="text-xs font-semibold uppercase text-slate-500">Tokens</span>
            <span className="mt-2 block text-xl font-bold text-slate-800">{totalTokens || "N/A"}</span>
          </Card>
          <Card className="p-4">
            <span className="text-xs font-semibold uppercase text-slate-500">Cost</span>
            <span className="mt-2 block text-xl font-bold text-amber-600">{formatCost(totalCost)}</span>
          </Card>
        </div>

        {trace.error ? (
          <Alert kind="error">Error: {trace.error}</Alert>
        ) : null}

        <Card title={`Spans (${spans.length})`}>
          {spans.length === 0 ? (
            <p className="text-sm text-slate-500">No spans recorded for this trace.</p>
          ) : (
            <div className="overflow-x-auto">
              {tree.map((node) => (
                <SpanRow key={node.span.span_id} node={node} depth={0} />
              ))}
            </div>
          )}
        </Card>

        {llmSpans.length > 0 ? (
          <Card title="LLM Invocations">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-slate-500">
                    <th className="py-2 pr-4">Provider</th>
                    <th className="py-2 pr-4">Model</th>
                    <th className="py-2 pr-4">Input Tokens</th>
                    <th className="py-2 pr-4">Output Tokens</th>
                    <th className="py-2 pr-4">Total Tokens</th>
                    <th className="py-2 pr-4">Latency</th>
                    <th className="py-2">Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {llmSpans.map((s) => (
                    <tr key={s.id} className="border-b">
                      <td className="py-2 pr-4 font-medium text-slate-900">{s.provider ?? "—"}</td>
                      <td className="py-2 pr-4 font-mono text-slate-800">{s.model ?? "—"}</td>
                      <td className="py-2 pr-4">{s.input_tokens ?? "—"}</td>
                      <td className="py-2 pr-4">{s.output_tokens ?? "—"}</td>
                      <td className="py-2 pr-4">{s.total_tokens ?? "—"}</td>
                      <td className="py-2 pr-4">{s.duration_ms != null ? `${s.duration_ms.toFixed(0)}ms` : "—"}</td>
                      <td className="py-2">{formatCost(s.estimated_cost)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        ) : null}
      </div>
    </AppShell>
  );
}
