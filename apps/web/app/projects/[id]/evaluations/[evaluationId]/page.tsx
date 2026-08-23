"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

const FAILURE_COLORS: Record<string, string> = {
  PASS: "bg-green-100 text-green-700",
  FAIL: "bg-red-100 text-red-700",
  ERROR: "bg-amber-100 text-amber-700",
  SKIPPED: "bg-slate-100 text-slate-600",
};

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
      return status === "QUEUED" || status === "RUNNING" ? 3000 : false;
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

  return (
    <AppShell>
      <Link href={`/projects/${projectId}/evaluations`} className="text-sm text-brand hover:underline">
        ← Evaluations
      </Link>
      <h1 className="mt-2 mb-4 text-2xl font-bold text-slate-900">
        Evaluation {evaluationId.slice(0, 8)}
      </h1>
      {error ? <Alert kind="error" className="mb-4">{error}</Alert> : null}

      {evaluation.isLoading ? (
        <Card><p className="text-sm text-slate-400">Loading evaluation…</p></Card>
      ) : evaluation.isError ? (
        <Card><Alert kind="error">{(evaluation.error as Error).message}</Alert></Card>
      ) : run ? (
        <>
          <div className="mb-6 grid gap-4 md:grid-cols-2">
            <Card title="Status">
              <div className="flex items-center gap-3">
                <span
                  className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                    run.status === "COMPLETED"
                      ? "bg-green-100 text-green-700"
                      : run.status === "FAILED"
                        ? "bg-red-100 text-red-700"
                        : "bg-slate-100 text-slate-700"
                  }`}
                >
                  {run.status}
                </span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full bg-brand transition-all"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <span className="text-sm text-slate-500">
                  {run.completed_tests}/{run.total_tests}
                </span>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                {run.status === "QUEUED" ? (
                  <Button onClick={() => runMutation.mutate()} disabled={runMutation.isPending}>
                    {runMutation.isPending ? "Starting…" : "Run now"}
                  </Button>
                ) : null}
                {run.status === "QUEUED" || run.status === "RUNNING" ? (
                  <Button variant="danger" onClick={() => cancelMutation.mutate()} disabled={cancelMutation.isPending}>
                    {cancelMutation.isPending ? "Cancelling…" : "Cancel"}
                  </Button>
                ) : null}
              </div>
            </Card>
            <Card title="Summary">
              <dl className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <dt className="text-slate-500">Passed</dt>
                  <dd className="font-medium text-slate-900">{run.passed_tests}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Failed</dt>
                  <dd className="font-medium text-slate-900">{run.failed_tests}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Errors</dt>
                  <dd className="font-medium text-slate-900">{run.error_tests}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Pass rate</dt>
                  <dd className="font-medium text-slate-900">
                    {metrics ? `${(metrics.pass_rate * 100).toFixed(1)}%` : "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-slate-500">Avg latency</dt>
                  <dd className="font-medium text-slate-900">
                    {metrics?.average_latency_ms != null ? `${metrics.average_latency_ms} ms` : "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-slate-500">p95 latency</dt>
                  <dd className="font-medium text-slate-900">
                    {metrics?.p95_latency_ms != null ? `${metrics.p95_latency_ms} ms` : "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-slate-500">Total tokens</dt>
                  <dd className="font-medium text-slate-900">{metrics?.total_tokens ?? 0}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Dataset checksum</dt>
                  <dd className="font-mono text-xs text-slate-900">
                    {run.dataset_checksum ? run.dataset_checksum.slice(0, 16) + "…" : "—"}
                  </dd>
                </div>
                {metrics?.average_judge_score != null ? (
                  <>
                    <div>
                      <dt className="text-slate-500">Avg judge score</dt>
                      <dd className="font-medium text-slate-900">{metrics.average_judge_score}</dd>
                    </div>
                    <div>
                      <dt className="text-slate-500">Avg confidence</dt>
                      <dd className="font-medium text-slate-900">{metrics.average_confidence ?? "—"}</dd>
                    </div>
                  </>
                ) : null}
              </dl>
            </Card>
          </div>

          <Card title="Results" className="mb-6">
            <div className="mb-4 flex flex-wrap gap-3 text-sm">
              <label className="flex items-center gap-2 text-slate-600">
                Status
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="rounded-md border border-slate-300 px-2 py-1"
                >
                  <option value="">All</option>
                  <option value="PASS">PASS</option>
                  <option value="FAIL">FAIL</option>
                  <option value="ERROR">ERROR</option>
                  <option value="SKIPPED">SKIPPED</option>
                </select>
              </label>
              <label className="flex items-center gap-2 text-slate-600">
                Failure type
                <select
                  value={failureFilter}
                  onChange={(e) => setFailureFilter(e.target.value)}
                  className="rounded-md border border-slate-300 px-2 py-1"
                >
                  <option value="">All</option>
                  <option value="ASSERTION_FAILED">ASSERTION_FAILED</option>
                  <option value="EVALUATOR_ERROR">EVALUATOR_ERROR</option>
                  <option value="TIMEOUT">TIMEOUT</option>
                  <option value="PROVIDER_ERROR">PROVIDER_ERROR</option>
                  <option value="INVALID_OUTPUT">INVALID_OUTPUT</option>
                </select>
              </label>
            </div>

            {results.isLoading ? (
              <p className="text-sm text-slate-400">Loading results…</p>
            ) : results.isError ? (
              <Alert kind="error">{(results.error as Error).message}</Alert>
            ) : !results.data?.data.length ? (
              <p className="text-sm text-slate-500">No results match the current filters.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-slate-500">
                      <th className="py-2 pr-4">Status</th>
                      <th className="py-2 pr-4">Failure</th>
                      <th className="py-2 pr-4">Latency</th>
                      <th className="py-2 pr-4">Tokens</th>
                      <th className="py-2 pr-4">Judge</th>
                      <th className="py-2">Actual output</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.data.data.map((res) => (
                      <tr key={res.id} className="border-b align-top">
                        <td className="py-2 pr-4">
                          <span
                            className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                              FAILURE_COLORS[res.status] ?? "bg-slate-100 text-slate-600"
                            }`}
                          >
                            {res.status}
                          </span>
                        </td>
                        <td className="py-2 pr-4">
                          {res.failure_type ? (
                            <div>
                              <span className="font-mono text-xs text-amber-700">{res.failure_type}</span>
                              {res.failure_message ? (
                                <p className="mt-1 max-w-xs text-xs text-slate-500">{res.failure_message}</p>
                              ) : null}
                            </div>
                          ) : (
                            <span className="text-slate-400">—</span>
                          )}
                        </td>
                        <td className="py-2 pr-4 text-slate-600">{res.latency_ms ?? "—"} ms</td>
                        <td className="py-2 pr-4 text-slate-600">{res.total_tokens ?? 0}</td>
                        <td className="py-2 pr-4">
                          {res.judge_score != null ? (
                            <div className="text-xs text-slate-600">
                              <p>
                                Score <span className="font-medium text-slate-900">{res.judge_score}</span>
                                {res.combined_score != null ? (
                                  <span className="text-slate-400"> (combined {res.combined_score})</span>
                                ) : null}
                              </p>
                              <p>
                                Confidence{" "}
                                <span className="font-medium text-slate-900">{res.judge_confidence ?? "—"}</span>
                              </p>
                              {res.judge_criteria_scores ? (
                                <div className="mt-1">
                                  {Object.entries(res.judge_criteria_scores).map(([k, v]) => (
                                    <p key={k} className="capitalize">
                                      {k}: <span className="font-medium">{v}</span>
                                    </p>
                                  ))}
                                </div>
                              ) : null}
                              {res.judge_reasoning ? (
                                <p className="mt-1 max-w-xs text-slate-500">{res.judge_reasoning}</p>
                              ) : null}
                              {res.judge_model_snapshot || res.judge_rubric_snapshot ? (
                                <p className="mt-1 text-slate-400">
                                  {String(res.judge_model_snapshot?.model_identifier ?? "judge")} · rubric v
                                  {String(res.judge_rubric_snapshot?.version ?? "?")} · prompt{" "}
                                  {res.judge_prompt_version ?? "?"}
                                </p>
                              ) : null}
                            </div>
                          ) : (
                            <span className="text-slate-400">—</span>
                          )}
                        </td>
                        <td className="py-2">
                          <p className="max-w-md truncate font-mono text-xs text-slate-600">
                            {res.actual_output ?? "—"}
                          </p>
                          {res.explanation ? (
                            <p className="mt-1 max-w-md text-xs text-slate-500">{res.explanation}</p>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      ) : null}
    </AppShell>
  );
}
