"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Alert } from "@/components/ui/Alert";
import { Card } from "@/components/ui/Card";

const SEVERITY_BADGES: Record<string, string> = {
  LOW: "bg-slate-100 text-slate-700 border-slate-200",
  MEDIUM: "bg-amber-50 text-amber-700 border-amber-200",
  HIGH: "bg-rose-50 text-rose-700 border-rose-200",
  CRITICAL: "bg-red-100 text-red-700 border-red-200",
};

const CONFIDENCE_BADGES: Record<string, string> = {
  LOW: "bg-slate-100 text-slate-600 border-slate-200",
  MEDIUM: "bg-blue-50 text-blue-700 border-blue-200",
  HIGH: "bg-emerald-50 text-emerald-700 border-emerald-200",
};

export default function BenchmarkRunDetailPage() {
  const params = useParams<{ id: string; runId: string }>();
  const projectId = params.id;
  const runId = params.runId;

  const detail = useQuery({
    queryKey: ["benchmark-run-detail", runId],
    queryFn: async () => {
      const res = await api.getBenchmarkRunDetail(runId);
      return res.data;
    },
    refetchInterval: (query) =>
      query.state.data?.run?.status === "QUEUED" || query.state.data?.run?.status === "RUNNING"
        ? 3000
        : false,
  });

  if (detail.isLoading) {
    return (
      <AppShell>
        <div className="flex flex-col gap-4">
          <p className="text-sm text-slate-400">Loading benchmark run details…</p>
        </div>
      </AppShell>
    );
  }

  if (detail.isError) {
    return (
      <AppShell>
        <Alert kind="error">{(detail.error as Error).message}</Alert>
      </AppShell>
    );
  }

  const { run, results, evidences, clusters, recommendation } = detail.data!;

  // SVG Gauge calculations
  const score = run.reliability_score ?? 0.0;
  const radius = 60;
  const stroke = 12;
  const normalizedRadius = radius - stroke * 2;
  const circumference = normalizedRadius * 2 * Math.PI;
  const strokeDashoffset = circumference - score * circumference;

  return (
    <AppShell>
      <div>
        <Link href={`/projects/${projectId}/benchmarks`} className="text-sm text-brand hover:underline">
          ← Benchmark History
        </Link>
        <div className="mt-2 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Benchmark Audit Report</h1>
            <p className="text-sm text-slate-500 mt-1">
              Detailed statistical comparison, reliability weighting score, and root-cause recommendations.
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span>Run ID: {run.id}</span>
            <span>•</span>
            <span>Methodology: v{run.methodology_version}</span>
          </div>
        </div>
      </div>

      <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left Column: Visual score and Recommendation */}
        <div className="lg:col-span-1 flex flex-col gap-6">
          {/* Gauge card */}
          <Card className="flex flex-col items-center justify-center p-6 text-center">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-6">
              Overall Reliability
            </h2>
            <div className="relative flex items-center justify-center">
              <svg height={radius * 2} width={radius * 2} className="transform -rotate-90">
                {/* Background track */}
                <circle
                  stroke="#e2e8f0"
                  fill="transparent"
                  strokeWidth={stroke}
                  r={normalizedRadius}
                  cx={radius}
                  cy={radius}
                />
                {/* Dynamic circle */}
                <circle
                  stroke={score >= 0.8 ? "#10b981" : score >= 0.6 ? "#3b82f6" : "#f43f5e"}
                  fill="transparent"
                  strokeWidth={stroke}
                  strokeDasharray={circumference + " " + circumference}
                  style={{ strokeDashoffset }}
                  strokeLinecap="round"
                  r={normalizedRadius}
                  cx={radius}
                  cy={radius}
                />
              </svg>
              <div className="absolute text-center">
                <span className="text-2xl font-bold text-slate-900">
                  {run.reliability_score !== null ? (score * 100).toFixed(0) + "%" : "—"}
                </span>
                <p className="text-[10px] text-slate-400 font-medium">INDEX SCORE</p>
              </div>
            </div>
            <div className="mt-6 flex flex-col gap-1 text-xs text-slate-500">
              <p>Status: <span className="font-semibold text-slate-800">{run.status}</span></p>
              {run.completed_at && (
                <p>Finished: <span className="font-normal text-slate-400">{new Date(run.completed_at).toLocaleString()}</span></p>
              )}
            </div>
          </Card>

          {/* Actionable recommendations */}
          {recommendation && (
            <Card className="p-6 flex flex-col gap-4">
              <div className="flex items-center justify-between border-b pb-3">
                <h2 className="text-sm font-bold text-slate-900">Root-Cause Analysis</h2>
                <span
                  className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold ${
                    CONFIDENCE_BADGES[recommendation.root_cause_confidence] || "bg-slate-100"
                  }`}
                >
                  {recommendation.root_cause_confidence} CONFIDENCE
                </span>
              </div>

              {recommendation.regression_attribution && (
                <div className="rounded-lg bg-rose-50 border border-rose-100 p-3 text-xs text-rose-800">
                  <p className="font-bold">Regression Attributed:</p>
                  <p className="mt-0.5">{recommendation.regression_attribution}</p>
                </div>
              )}

              <div className="text-xs text-slate-600 flex flex-col gap-3">
                <div>
                  <p className="font-bold text-slate-700">Analysis Summary:</p>
                  <p className="mt-1 leading-relaxed">{recommendation.root_cause_analysis}</p>
                </div>
                <div>
                  <p className="font-bold text-slate-700">Actionable Suggestion:</p>
                  <p className="mt-1 leading-relaxed p-2 bg-slate-50 border rounded-lg font-mono text-slate-700">
                    {recommendation.recommendation}
                  </p>
                </div>
              </div>
            </Card>
          )}
        </div>

        {/* Right Column: Comparative results, evidences, failure clustering */}
        <div className="lg:col-span-2 flex flex-col gap-6">
          {/* Candidate Variant Summary */}
          <div>
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">Model Variant scores</h2>
            <Card className="overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-slate-500 bg-slate-50/50">
                    <th className="py-2.5 px-4">Evaluation Run ID</th>
                    <th className="py-2.5 px-4">Model ID</th>
                    <th className="py-2.5 px-4">Reliability Score</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((res) => (
                    <tr key={res.id} className="border-b last:border-0 hover:bg-slate-50/50">
                      <td className="py-3 px-4 font-semibold text-slate-900">{res.evaluation_run_id.slice(0, 8)}…</td>
                      <td className="py-3 px-4 text-slate-600 text-xs truncate max-w-xs">{res.model_id}</td>
                      <td className="py-3 px-4 font-bold text-slate-800">{(res.reliability_score * 100).toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          </div>

          {/* Statistical Evidence details */}
          <div>
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">Statistical Evidence</h2>
            <Card className="overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-slate-500 bg-slate-50/50">
                    <th className="py-2.5 px-4">Metric</th>
                    <th className="py-2.5 px-4 text-right">Baseline Mean</th>
                    <th className="py-2.5 px-4 text-right">Candidate Mean</th>
                    <th className="py-2.5 px-4 text-right">Abs Change</th>
                    <th className="py-2.5 px-4 text-center">Significant</th>
                    <th className="py-2.5 px-4 text-center">Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {evidences.map((ev) => (
                    <tr key={ev.id} className="border-b last:border-0 hover:bg-slate-50/50">
                      <td className="py-3 px-4 font-semibold text-slate-900">{ev.metric_name}</td>
                      <td className="py-3 px-4 text-right text-slate-600">{ev.baseline_value.toFixed(4)}</td>
                      <td className="py-3 px-4 text-right text-slate-600">{ev.candidate_value.toFixed(4)}</td>
                      <td className={`py-3 px-4 text-right font-semibold ${
                        ev.absolute_change < 0 ? "text-rose-600" : ev.absolute_change > 0 ? "text-emerald-600" : "text-slate-500"
                      }`}>
                        {ev.absolute_change >= 0 ? "+" : ""}{ev.absolute_change.toFixed(4)}
                      </td>
                      <td className="py-3 px-4 text-center">
                        <span className={`inline-flex items-center rounded-md px-1.5 py-0.5 text-xs font-semibold ${
                          ev.significance ? "bg-rose-50 text-rose-700" : "bg-slate-100 text-slate-600"
                        }`}>
                          {ev.significance ? "Yes" : "No"}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-center">
                        <span className={`inline-flex items-center rounded-md px-1.5 py-0.5 text-xs font-semibold ${
                          CONFIDENCE_BADGES[ev.confidence] || "bg-slate-100 text-slate-600"
                        }`}>
                          {ev.confidence}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          </div>

          {/* Failure Clusters */}
          <div>
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">Deterministic Failure Clusters</h2>
            <Card className="overflow-hidden">
              {clusters.length === 0 ? (
                <div className="p-6 text-center">
                  <p className="text-sm text-slate-400">No failure clusters generated for this run.</p>
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-slate-500 bg-slate-50/50">
                      <th className="py-2.5 px-4">Failure Mode Pattern</th>
                      <th className="py-2.5 px-4 text-center">Count</th>
                      <th className="py-2.5 px-4 text-center">Percentage</th>
                      <th className="py-2.5 px-4 text-center">Severity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {clusters.map((cl) => (
                      <tr key={cl.id} className="border-b last:border-0 hover:bg-slate-50/50">
                        <td className="py-3 px-4 font-mono text-xs text-slate-700 max-w-sm truncate">{cl.error_message_pattern}</td>
                        <td className="py-3 px-4 text-center font-semibold text-slate-900">{cl.cluster_count}</td>
                        <td className="py-3 px-4 text-center text-slate-600">{(cl.cluster_percentage * 100).toFixed(1)}%</td>
                        <td className="py-3 px-4 text-center">
                          <span className={`inline-flex items-center rounded-md border px-1.5 py-0.5 text-xs font-semibold ${
                            SEVERITY_BADGES[cl.severity] || "bg-slate-100"
                          }`}>
                            {cl.severity}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
