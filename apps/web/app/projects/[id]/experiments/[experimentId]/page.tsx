"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

const STATUS_STYLES: Record<string, string> = {
  DRAFT: "bg-slate-100 text-slate-600",
  QUEUED: "bg-slate-100 text-slate-600",
  RUNNING: "bg-blue-100 text-blue-700",
  COMPLETED: "bg-green-100 text-green-700",
  FAILED: "bg-red-100 text-red-700",
  CANCELLED: "bg-slate-100 text-slate-500",
  PASS: "bg-green-100 text-green-700",
  FAIL: "bg-red-100 text-red-700",
  INCONCLUSIVE: "bg-amber-100 text-amber-700",
};

const SEVERITY_STYLES: Record<string, string> = {
  NONE: "bg-slate-100 text-slate-600",
  LOW: "bg-blue-100 text-blue-700",
  MEDIUM: "bg-amber-100 text-amber-700",
  HIGH: "bg-orange-100 text-orange-700",
  CRITICAL: "bg-red-100 text-red-700",
};

export default function ExperimentDetailPage() {
  const params = useParams<{ id: string; experimentId: string }>();
  const projectId = params.id;
  const experimentId = params.experimentId;
  const queryClient = useQueryClient();

  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Queries
  const experiment = useQuery({
    queryKey: ["experiment", experimentId],
    queryFn: () => api.getExperiment(experimentId),
  });

  const runs = useQuery({
    queryKey: ["experiment-runs", experimentId],
    queryFn: () => api.listExperimentRuns(experimentId),
    refetchInterval: (query) =>
      query.state.data?.data.some((r) => r.status === "QUEUED" || r.status === "RUNNING")
        ? 3000
        : false,
  });

  const ciRuns = useQuery({
    queryKey: ["ci-runs-lookup", projectId],
    queryFn: () => api.listCIRuns(projectId, { page_size: 100 }),
    enabled: !!projectId,
  });

  const linkedCIRun = ciRuns.data?.data.find((r) => r.experiment_id === experimentId);

  // Set default selected run as the latest run when runs load
  useEffect(() => {
    if (runs.data?.data && runs.data.data.length > 0 && !selectedRunId) {
      setSelectedRunId(runs.data.data[0].id);
    }
  }, [runs.data, selectedRunId]);

  // Invalidate and refetch subresources when the selected run transitions to a terminal status
  const selectedRunStatus = runs.data?.data.find((r) => r.id === selectedRunId)?.status;
  useEffect(() => {
    if (
      selectedRunStatus === "COMPLETED" ||
      selectedRunStatus === "FAILED" ||
      selectedRunStatus === "CANCELLED"
    ) {
      queryClient.invalidateQueries({ queryKey: ["experiment-results", selectedRunId] });
      queryClient.invalidateQueries({ queryKey: ["experiment-regressions", selectedRunId] });
      queryClient.invalidateQueries({ queryKey: ["experiment-quality-gates", selectedRunId] });
    }
  }, [selectedRunStatus, selectedRunId, queryClient]);

  const results = useQuery({
    queryKey: ["experiment-results", selectedRunId],
    queryFn: () => api.getExperimentResults(selectedRunId!),
    enabled: !!selectedRunId,
  });

  const regressions = useQuery({
    queryKey: ["experiment-regressions", selectedRunId],
    queryFn: () => api.getExperimentRegressions(selectedRunId!),
    enabled: !!selectedRunId,
  });

  const qualityGates = useQuery({
    queryKey: ["experiment-quality-gates", selectedRunId],
    queryFn: () => api.getExperimentQualityGates(selectedRunId!),
    enabled: !!selectedRunId,
  });

  // Mutations
  const runMutation = useMutation({
    mutationFn: () => api.runExperiment(experimentId),
    onSuccess: (data) => {
      setSelectedRunId(data.data.id);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["experiment", experimentId] });
      queryClient.invalidateQueries({ queryKey: ["experiment-runs", experimentId] });
    },
    onError: (err) => {
      setError(err instanceof ApiClientError ? err.message : "Failed to run experiment");
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (runId: string) => api.cancelExperimentRun(runId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["experiment", experimentId] });
      queryClient.invalidateQueries({ queryKey: ["experiment-runs", experimentId] });
    },
    onError: (err) => {
      setError(err instanceof ApiClientError ? err.message : "Failed to cancel run");
    },
  });

  const activeRun = runs.data?.data.find((r) => r.status === "QUEUED" || r.status === "RUNNING");

  return (
    <AppShell>
      <div className="flex items-center justify-between">
        <div>
          <Link href={`/projects/${projectId}/experiments`} className="text-sm text-brand hover:underline">
            ← Experiments
          </Link>
          <h1 className="mt-2 text-2xl font-bold text-slate-900">{experiment.data?.data.name}</h1>
          <p className="text-sm text-slate-500 mt-1 max-w-2xl">{experiment.data?.data.description}</p>
        </div>
        <div className="flex gap-2">
          {activeRun ? (
            <Button
              variant="danger"
              onClick={() => cancelMutation.mutate(activeRun.id)}
              disabled={cancelMutation.isPending}
            >
              Cancel Active Run
            </Button>
          ) : (
            <Button onClick={() => runMutation.mutate()} disabled={runMutation.isPending}>
              Run Experiment
            </Button>
          )}
        </div>
      </div>

      {error && <Alert kind="error" className="mt-4 mb-2">{error}</Alert>}

      <div className="grid gap-6 md:grid-cols-3 mt-6">
        {/* Left Side: Metadata and Runs History */}
        <div className="flex flex-col gap-6 md:col-span-1">
          <Card title="Experiment Setup">
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-slate-500 font-semibold">Type</dt>
                <dd className="text-slate-800 font-medium">{experiment.data?.data.experiment_type.replace("_", " ")}</dd>
              </div>
              <div>
                <dt className="text-slate-500 font-semibold">Status / Gate Outcome</dt>
                <dd className="mt-0.5">
                  <span
                    className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                      STATUS_STYLES[experiment.data?.data.status ?? ""] ?? "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {experiment.data?.data.status}
                  </span>
                </dd>
              </div>
              <div>
                <dt className="text-slate-500 font-semibold">Config Fingerprint</dt>
                <dd className="text-slate-700 font-mono text-xs truncate max-w-xs">{experiment.data?.data.fingerprint}</dd>
              </div>
            </dl>
          </Card>

          {linkedCIRun && (
            <Card title="Git & CI Provenance">
              <dl className="space-y-3 text-sm">
                <div>
                  <dt className="text-slate-500 font-semibold">Repository</dt>
                  <dd className="text-slate-800 font-medium">{linkedCIRun.repository}</dd>
                </div>
                <div>
                  <dt className="text-slate-500 font-semibold">Branch</dt>
                  <dd className="text-slate-800 font-mono text-xs">{linkedCIRun.branch}</dd>
                </div>
                <div>
                  <dt className="text-slate-500 font-semibold">Commit SHA</dt>
                  <dd className="text-slate-800 font-mono text-xs">{linkedCIRun.commit_sha.substring(0, 8)}</dd>
                </div>
                {linkedCIRun.pull_request_number && (
                  <div>
                    <dt className="text-slate-500 font-semibold">Pull Request</dt>
                    <dd className="text-slate-800 text-xs">
                      <a
                        href={linkedCIRun.pull_request_url || "#"}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-brand hover:underline font-semibold"
                      >
                        PR #{linkedCIRun.pull_request_number}
                      </a>
                    </dd>
                  </div>
                )}
                <div>
                  <dt className="text-slate-500 font-semibold">CI Run ID</dt>
                  <dd className="text-slate-800 font-mono text-xs">{linkedCIRun.ci_run_id}</dd>
                </div>
                <div>
                  <dt className="text-slate-500 font-semibold">CI Provider</dt>
                  <dd className="text-slate-800 font-mono text-xs">{linkedCIRun.ci_provider}</dd>
                </div>
              </dl>
            </Card>
          )}

          <Card title="Runs History">
            {runs.isLoading ? (
              <p className="text-xs text-slate-400">Loading runs…</p>
            ) : !runs.data?.data.length ? (
              <p className="text-xs text-slate-500">No runs recorded.</p>
            ) : (
              <div className="divide-y overflow-y-auto max-h-80">
                {runs.data.data.map((r, i) => (
                  <button
                    key={r.id}
                    onClick={() => setSelectedRunId(r.id)}
                    className={`w-full text-left py-2 px-3 hover:bg-slate-50 flex flex-col gap-1 transition-colors ${
                      selectedRunId === r.id ? "bg-slate-100 hover:bg-slate-100 border-l-4 border-brand" : ""
                    }`}
                  >
                    <div className="flex justify-between items-center text-xs font-semibold text-slate-700">
                      <span>Run #{runs.data.data.length - i}</span>
                      <span className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-bold ${STATUS_STYLES[r.status]}`}>
                        {r.status}
                      </span>
                    </div>
                    <span className="text-[10px] text-slate-400">
                      {new Date(r.created_at).toLocaleString()}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* Right Side: Selected Run Details (Comparisons, Regressions, Quality Gates) */}
        <div className="md:col-span-2 flex flex-col gap-6">
          {selectedRunId ? (
            <>
              {/* Comparisons Dashboard */}
              <Card title="Comparisons dashboard">
                {results.isLoading ? (
                  <p className="text-sm text-slate-400">Loading comparison dashboard…</p>
                ) : !results.data?.data.length ? (
                  <p className="text-sm text-slate-500">No comparisons available for this run status.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left">
                      <thead>
                        <tr className="border-b text-slate-500">
                          <th className="py-2 pr-2">Metric</th>
                          <th className="py-2 pr-2">Baseline</th>
                          <th className="py-2 pr-2">Candidate</th>
                          <th className="py-2 pr-2">Change</th>
                          <th className="py-2 pr-2">Classification</th>
                          <th className="py-2">P-value / CI</th>
                        </tr>
                      </thead>
                      <tbody>
                        {results.data.data.map((res) => {
                          const relChange = res.relative_difference !== null ? `${(res.relative_difference * 100).toFixed(1)}%` : "0%";
                          const isBetter = res.classification === "IMPROVED";
                          const isWorse = res.classification === "REGRESSED";
                          
                          // Format CI/Pvalue
                          let statsStr = "N/A";
                          if (res.statistical_metadata) {
                            const p = res.statistical_metadata.p_value as number | null | undefined;
                            const ci_c_l = res.statistical_metadata.ci_candidate_lower as number | null | undefined;
                            const ci_c_u = res.statistical_metadata.ci_candidate_upper as number | null | undefined;
                            statsStr = `p=${(p !== null && p !== undefined) ? p.toFixed(4) : "N/A"}`;
                            if (ci_c_l !== undefined && ci_c_l !== null && ci_c_u !== undefined && ci_c_u !== null) {
                              statsStr += ` [${ci_c_l.toFixed(2)}, ${ci_c_u.toFixed(2)}]`;
                            }
                          }

                          return (
                            <tr key={res.id} className="border-b">
                              <td className="py-2 pr-2 font-medium text-slate-900">{res.metric_name}</td>
                              <td className="py-2 pr-2 text-slate-600">{res.baseline_value !== null ? res.baseline_value.toFixed(4) : "N/A"}</td>
                              <td className="py-2 pr-2 text-slate-600">{res.candidate_value !== null ? res.candidate_value.toFixed(4) : "N/A"}</td>
                              <td className={`py-2 pr-2 font-semibold ${isBetter ? "text-green-600" : isWorse ? "text-red-600" : "text-slate-500"}`}>
                                {res.absolute_difference !== null ? `${res.absolute_difference > 0 ? "+" : ""}${res.absolute_difference.toFixed(4)} (${relChange})` : "0"}
                              </td>
                              <td className="py-2 pr-2">
                                <span className={`inline-block rounded px-1.5 py-0.5 text-xs font-semibold ${STATUS_STYLES[res.classification]}`}>
                                  {res.classification.replace("_", " ")}
                                </span>
                              </td>
                              <td className="py-2 font-mono text-[10px] text-slate-400">{statsStr}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </Card>

              {/* Regressions Alert Section */}
              <Card title="Detected Regressions">
                {regressions.isLoading ? (
                  <p className="text-sm text-slate-400">Loading regressions…</p>
                ) : !regressions.data?.data.length ? (
                  <p className="text-sm text-green-600 font-semibold">✓ No regressions detected for this run.</p>
                ) : (
                  <div className="space-y-3">
                    {regressions.data.data.map((reg) => (
                      <div key={reg.id} className="p-3 border rounded-md flex justify-between items-start bg-red-50/20 border-red-200">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className={`px-2 py-0.5 text-[10px] uppercase font-bold rounded-full ${SEVERITY_STYLES[reg.severity]}`}>
                              {reg.severity}
                            </span>
                            <span className="text-sm font-bold text-slate-800">{reg.metric_name}</span>
                          </div>
                          <p className="text-xs text-slate-500 mt-1">{reg.explanation}</p>
                        </div>
                        <div className="text-xs text-right text-slate-600">
                          <div>Baseline: {reg.baseline_value?.toFixed(4)}</div>
                          <div>Candidate: {reg.candidate_value?.toFixed(4)}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Card>

              {/* Quality Gates Result list */}
              <Card title="Quality Gates Checklist">
                {qualityGates.isLoading ? (
                  <p className="text-sm text-slate-400">Loading quality gates…</p>
                ) : !qualityGates.data?.data.length ? (
                  <p className="text-sm text-slate-500">No quality gates configured.</p>
                ) : (
                  <div className="space-y-2">
                    {qualityGates.data.data.map((gate) => (
                      <div key={gate.id} className="flex justify-between items-center py-2 px-3 border rounded-md">
                        <div className="flex flex-col gap-0.5">
                          <span className="text-sm font-semibold text-slate-700">{gate.metric_name}</span>
                          <span className="text-xs text-slate-400 font-mono">Actual: {gate.actual_value !== null ? gate.actual_value.toFixed(4) : "N/A"}</span>
                        </div>
                        <span className={`px-2.5 py-0.5 text-xs font-bold rounded ${STATUS_STYLES[gate.status]}`}>
                          {gate.status}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            </>
          ) : (
            <Card>
              <p className="text-sm text-slate-400 text-center py-10">Select a run from the history to view results.</p>
            </Card>
          )}
        </div>
      </div>
    </AppShell>
  );
}
