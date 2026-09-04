"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, MetricCard } from "@/components/ui/Card";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { Select } from "@/components/ui/Input";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/Table";

export default function EvaluationDetailPage() {
  const params = useParams<{ id: string; evaluationId: string }>();
  const projectId = params.id;
  const evaluationId = params.evaluationId;
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [failureFilter, setFailureFilter] = useState("");

  const evaluation = useQuery({
    queryKey: ["evaluation", evaluationId],
    queryFn: () => api.getEvaluation(evaluationId),
    refetchInterval: (query) => {
      const status = query.state.data?.data.status;
      return status === "QUEUED" || status === "RUNNING" ? 2000 : false;
    },
  });

  const results = useQuery({
    queryKey: ["evaluation-results", evaluationId, statusFilter, failureFilter],
    queryFn: () =>
      api.listEvaluationResults(evaluationId, {
        page: 1,
        page_size: 100,
        status: statusFilter || undefined,
        failure_type: failureFilter || undefined,
      }),
    enabled: Boolean(evaluation.data?.data.status === "COMPLETED" || evaluation.data?.data.status === "FAILED"),
  });

  const runMutation = useMutation({
    mutationFn: () => api.runEvaluation(evaluationId),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["evaluation", evaluationId] });
    },
    onError: (e) => setError(e instanceof ApiClientError ? e.message : "Failed to start evaluation"),
  });

  const cancelMutation = useMutation({
    mutationFn: () => api.cancelEvaluation(evaluationId),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["evaluation", evaluationId] });
    },
    onError: (e) => setError(e instanceof ApiClientError ? e.message : "Failed to cancel evaluation"),
  });

  const run = evaluation.data?.data;
  const metrics = run?.metrics;
  const progress = run && run.total_tests > 0 ? Math.round((run.completed_tests / run.total_tests) * 100) : 0;
  const passRate = metrics ? (metrics.pass_rate * 100).toFixed(1) : (run?.total_tests ? ((run.passed_tests / run.total_tests) * 100).toFixed(1) : "0.0");

  return (
    <AppShell>
      <div className="space-y-6" data-testid="evaluation-detail-view">
        {/* Breadcrumbs & Header */}
        <div className="border-b border-slate-200 pb-5">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 mb-1">
            <Link href={`/projects/${projectId}/evaluations`} className="hover:text-slate-900 transition">
              ← Back to Evaluations
            </Link>
          </div>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight text-slate-900" data-testid="evaluation-run-title">
                Evaluation Report
              </h1>
              <span className="font-mono text-xs text-slate-600 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                {evaluationId.slice(0, 12)}
              </span>
              <StatusBadge status={run?.status} />
            </div>

            <div className="flex items-center gap-2">
              {run?.status === "QUEUED" && (
                <Button
                  onClick={() => runMutation.mutate()}
                  disabled={runMutation.isPending}
                  isLoading={runMutation.isPending}
                  data-testid="eval-run-now-btn"
                >
                  Start Execution
                </Button>
              )}
              {(run?.status === "QUEUED" || run?.status === "RUNNING") && (
                <Button
                  variant="danger"
                  onClick={() => cancelMutation.mutate()}
                  disabled={cancelMutation.isPending}
                >
                  Cancel
                </Button>
              )}
            </div>
          </div>
        </div>

        {error ? <Alert kind="error">{error}</Alert> : null}

        {evaluation.isLoading ? (
          <div className="p-12 text-center text-slate-400">Loading evaluation report…</div>
        ) : evaluation.isError ? (
          <Alert kind="error">{(evaluation.error as Error).message}</Alert>
        ) : run ? (
          <>
            {/* Top KPI Metric Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4" data-testid="eval-metrics-grid">
              <MetricCard
                label="Quality Gate Pass Rate"
                value={`${passRate}%`}
                subvalue={`${run.passed_tests} passed / ${run.total_tests} total`}
                accent={Number(passRate) >= 80 ? "success" : "warning"}
                testId="eval-pass-rate"
              />
              <MetricCard
                label="Average Latency"
                value={metrics?.average_latency_ms != null ? `${metrics.average_latency_ms} ms` : "—"}
                subvalue={metrics?.p95_latency_ms != null ? `p95: ${metrics.p95_latency_ms} ms` : "Deterministic"}
                accent="brand"
                testId="eval-latency"
              />
              <MetricCard
                label="Failed / Errors"
                value={`${run.failed_tests} / ${run.error_tests}`}
                subvalue="Regression failures"
                accent={run.failed_tests > 0 ? "danger" : "neutral"}
                testId="eval-failed-count"
              />
              <MetricCard
                label="Total Tokens Consumed"
                value={metrics?.total_tokens ?? 0}
                subvalue="Inference footprint"
                accent="neutral"
                testId="eval-tokens"
              />
            </div>

            {/* Execution Progress & Configuration */}
            <Card title="Execution Summary" className="shadow-sm">
              <div className="space-y-4">
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs font-semibold text-slate-600">
                    <span>Execution Progress</span>
                    <span>{progress}% ({run.completed_tests}/{run.total_tests} completed)</span>
                  </div>
                  <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                    <div
                      className="h-full bg-brand-600 transition-all duration-300"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-3 border-t border-slate-100 text-xs">
                  <div>
                    <span className="text-slate-500 block">Dataset Checksum</span>
                    <span className="font-mono text-slate-800 font-semibold truncate block mt-0.5">
                      {run.dataset_checksum ? run.dataset_checksum.slice(0, 18) : "—"}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Execution Started</span>
                    <span className="text-slate-800 font-mono mt-0.5 block">
                      {new Date(run.created_at).toLocaleString()}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Judge Model Score</span>
                    <span className="text-slate-800 font-bold mt-0.5 block">
                      {metrics?.average_judge_score ?? "—"}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Judge Confidence</span>
                    <span className="text-slate-800 font-bold mt-0.5 block">
                      {metrics?.average_confidence ? `${(metrics.average_confidence * 100).toFixed(0)}%` : "—"}
                    </span>
                  </div>
                </div>
              </div>
            </Card>

            {/* Test Case Results Table */}
            <Card title="Individual Test Case Results" subtitle="Detailed input, expected output, and assertion scores" className="shadow-sm">
              <div className="mb-4 flex flex-wrap gap-3 text-sm">
                <Select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="sm:w-36"
                >
                  <option value="">All Statuses</option>
                  <option value="PASS">PASS</option>
                  <option value="FAIL">FAIL</option>
                  <option value="ERROR">ERROR</option>
                </Select>

                <Select
                  value={failureFilter}
                  onChange={(e) => setFailureFilter(e.target.value)}
                  className="sm:w-48"
                >
                  <option value="">All Failure Types</option>
                  <option value="ASSERTION_FAILED">ASSERTION_FAILED</option>
                  <option value="TIMEOUT">TIMEOUT</option>
                  <option value="PROVIDER_ERROR">PROVIDER_ERROR</option>
                </Select>
              </div>

              {results.isLoading ? (
                <div className="p-8 text-center text-slate-400">Loading results…</div>
              ) : results.isError ? (
                <Alert kind="error">{(results.error as Error).message}</Alert>
              ) : !results.data?.data.length ? (
                <p className="text-sm text-slate-500 py-4 text-center">No results match filter.</p>
              ) : (
                <Table>
                  <TableHeader>
                    <tr>
                      <TableHead>Status</TableHead>
                      <TableHead>Failure / Error</TableHead>
                      <TableHead>Latency</TableHead>
                      <TableHead>Tokens</TableHead>
                      <TableHead>Judge Score</TableHead>
                      <TableHead className="w-1/3">Model Output & Explanation</TableHead>
                    </tr>
                  </TableHeader>
                  <TableBody>
                    {results.data.data.map((res) => (
                      <TableRow key={res.id}>
                        <TableCell>
                          <StatusBadge status={res.status} />
                        </TableCell>
                        <TableCell>
                          {res.failure_type ? (
                            <span className="font-mono text-xs text-rose-700 bg-rose-50 px-2 py-0.5 rounded border border-rose-200">
                              {res.failure_type}
                            </span>
                          ) : (
                            <span className="text-xs text-slate-400">—</span>
                          )}
                        </TableCell>
                        <TableCell className="font-mono text-xs text-slate-700">
                          {res.latency_ms ?? "—"} ms
                        </TableCell>
                        <TableCell className="font-mono text-xs text-slate-700">
                          {res.total_tokens ?? 0}
                        </TableCell>
                        <TableCell>
                          {res.judge_score != null ? (
                            <span className="font-mono text-xs font-bold text-slate-900">
                              {res.judge_score}
                            </span>
                          ) : (
                            <span className="text-xs text-slate-400">—</span>
                          )}
                        </TableCell>
                        <TableCell>
                          <p className="font-mono text-xs text-slate-800 line-clamp-2">
                            {res.actual_output ?? "—"}
                          </p>
                          {res.judge_reasoning ? (
                            <p className="mt-1 text-xs text-slate-600 bg-slate-50 p-1.5 rounded border border-slate-100 line-clamp-3">
                              <span className="font-semibold text-slate-700">Judge: </span>
                              {res.judge_reasoning}
                            </p>
                          ) : res.explanation ? (
                            <p className="mt-1 text-xs text-slate-500">{res.explanation}</p>
                          ) : null}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </Card>
          </>
        ) : null}
      </div>
    </AppShell>
  );
}
