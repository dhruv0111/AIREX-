"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, MetricCard } from "@/components/ui/Card";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/Table";

const SEVERITY_VARIANTS: Record<string, "neutral" | "brand" | "warning" | "danger"> = {
  NONE: "neutral",
  LOW: "brand",
  MEDIUM: "warning",
  HIGH: "warning",
  CRITICAL: "danger",
};

export default function ExperimentDetailPage() {
  const params = useParams<{ id: string; experimentId: string }>();
  const projectId = params.id;
  const experimentId = params.experimentId;
  const queryClient = useQueryClient();

  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  useEffect(() => {
    if (runs.data?.data && runs.data.data.length > 0 && !selectedRunId) {
      setSelectedRunId(runs.data.data[0].id);
    }
  }, [runs.data, selectedRunId]);

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
  const exp = experiment.data?.data;

  return (
    <AppShell>
      <div className="space-y-6" data-testid="experiment-detail-view">
        {/* Breadcrumb & Header */}
        <div className="border-b border-slate-200 pb-5">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 mb-1">
            <Link href={`/projects/${projectId}/experiments`} className="hover:text-slate-900 transition">
              ← Back to Experiments
            </Link>
          </div>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold tracking-tight text-slate-900">
                  {exp?.name ?? "Experiment Analysis"}
                </h1>
                <StatusBadge status={exp?.status} />
              </div>
              <p className="text-xs text-slate-500 mt-1 max-w-2xl">{exp?.description}</p>
            </div>
            <div className="flex gap-2">
              {activeRun ? (
                <Button
                  variant="danger"
                  onClick={() => cancelMutation.mutate(activeRun.id)}
                  disabled={cancelMutation.isPending}
                >
                  Cancel Run
                </Button>
              ) : (
                <Button
                  onClick={() => runMutation.mutate()}
                  disabled={runMutation.isPending}
                  isLoading={runMutation.isPending}
                  data-testid="run-experiment-btn"
                >
                  Run A/B Benchmark
                </Button>
              )}
            </div>
          </div>
        </div>

        {error && <Alert kind="error">{error}</Alert>}

        <div className="grid gap-6 md:grid-cols-3">
          {/* Left Column: Config & Run History */}
          <div className="flex flex-col gap-6 md:col-span-1">
            <Card title="Experiment Specification" className="shadow-sm">
              <dl className="space-y-3 text-sm">
                <div className="flex justify-between py-1 border-b border-slate-100">
                  <dt className="text-slate-500">Experiment Type</dt>
                  <dd className="font-semibold text-slate-800">{exp?.experiment_type.replace(/_/g, " ")}</dd>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-100">
                  <dt className="text-slate-500">Quality Gate</dt>
                  <dd><StatusBadge status={exp?.status} /></dd>
                </div>
                <div className="py-1">
                  <dt className="text-slate-500 text-xs">Config Fingerprint</dt>
                  <dd className="font-mono text-xs text-slate-600 truncate mt-0.5">{exp?.fingerprint}</dd>
                </div>
              </dl>
            </Card>

            {linkedCIRun && (
              <Card title="CI/CD Provenance" className="shadow-sm">
                <dl className="space-y-2.5 text-xs">
                  <div className="flex justify-between"><dt className="text-slate-500">Repository</dt><dd className="font-medium text-slate-800">{linkedCIRun.repository}</dd></div>
                  <div className="flex justify-between"><dt className="text-slate-500">Branch</dt><dd className="font-mono text-slate-800">{linkedCIRun.branch}</dd></div>
                  <div className="flex justify-between"><dt className="text-slate-500">Commit SHA</dt><dd className="font-mono text-slate-800">{linkedCIRun.commit_sha.substring(0, 8)}</dd></div>
                  <div className="flex justify-between"><dt className="text-slate-500">CI Provider</dt><dd className="font-mono text-slate-800">{linkedCIRun.ci_provider}</dd></div>
                </dl>
              </Card>
            )}

            <Card title="Execution Runs" className="shadow-sm">
              {runs.isLoading ? (
                <p className="text-xs text-slate-400 py-4 text-center">Loading runs…</p>
              ) : !runs.data?.data.length ? (
                <p className="text-xs text-slate-500 py-4 text-center">No runs recorded.</p>
              ) : (
                <div className="divide-y divide-slate-100 overflow-y-auto max-h-80 -mx-6 -my-4">
                  {runs.data.data.map((r, i) => (
                    <button
                      key={r.id}
                      onClick={() => setSelectedRunId(r.id)}
                      className={`w-full text-left py-3 px-6 hover:bg-slate-50 flex flex-col gap-1 transition-colors ${
                        selectedRunId === r.id ? "bg-brand-50/50 border-l-4 border-brand-600" : ""
                      }`}
                    >
                      <div className="flex justify-between items-center text-xs font-semibold text-slate-800">
                        <span>Run #{runs.data.data.length - i}</span>
                        <StatusBadge status={r.status} />
                      </div>
                      <span className="text-[11px] text-slate-400 font-mono">
                        {new Date(r.created_at).toLocaleString()}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </Card>
          </div>

          {/* Right Column: Comparative Metrics, Regressions & Quality Gates */}
          <div className="md:col-span-2 flex flex-col gap-6">
            {selectedRunId ? (
              <>
                {/* Metric Comparisons Table */}
                <Card title="Candidate vs. Baseline Metric Deltas" subtitle="Calculated differences with empirical statistical validation" className="shadow-sm">
                  {results.isLoading ? (
                    <div className="p-8 text-center text-slate-400">Loading comparison metrics…</div>
                  ) : !results.data?.data.length ? (
                    <p className="text-sm text-slate-500 py-6 text-center">No metric comparisons computed for this run.</p>
                  ) : (
                    <Table>
                      <TableHeader>
                        <tr>
                          <TableHead>Metric</TableHead>
                          <TableHead>Baseline</TableHead>
                          <TableHead>Candidate</TableHead>
                          <TableHead>Delta</TableHead>
                          <TableHead>Classification</TableHead>
                          <TableHead>P-Value / CI</TableHead>
                        </tr>
                      </TableHeader>
                      <TableBody>
                        {results.data.data.map((res) => {
                          const relChange = res.relative_difference !== null ? `${(res.relative_difference * 100).toFixed(1)}%` : "0%";
                          const isBetter = res.classification === "IMPROVED";
                          const isWorse = res.classification === "REGRESSED";
                          
                          let statsStr = "N/A";
                          if (res.statistical_metadata) {
                            const p = res.statistical_metadata.p_value as number | null | undefined;
                            statsStr = `p=${(p !== null && p !== undefined) ? p.toFixed(4) : "N/A"}`;
                          }

                          return (
                            <TableRow key={res.id}>
                              <TableCell className="font-semibold text-slate-900">{res.metric_name}</TableCell>
                              <TableCell className="font-mono text-xs text-slate-600">{res.baseline_value !== null ? res.baseline_value.toFixed(4) : "—"}</TableCell>
                              <TableCell className="font-mono text-xs text-slate-900 font-semibold">{res.candidate_value !== null ? res.candidate_value.toFixed(4) : "—"}</TableCell>
                              <TableCell className={`font-mono text-xs font-bold ${isBetter ? "text-emerald-700" : isWorse ? "text-rose-700" : "text-slate-600"}`}>
                                {res.absolute_difference !== null ? `${res.absolute_difference > 0 ? "+" : ""}${res.absolute_difference.toFixed(4)} (${relChange})` : "0"}
                              </TableCell>
                              <TableCell>
                                <Badge variant={isBetter ? "success" : isWorse ? "danger" : "neutral"}>
                                  {res.classification.replace(/_/g, " ")}
                                </Badge>
                              </TableCell>
                              <TableCell className="font-mono text-[11px] text-slate-500">{statsStr}</TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  )}
                </Card>

                {/* Detected Regressions */}
                <Card title="Regression Analysis" className="shadow-sm">
                  {regressions.isLoading ? (
                    <p className="text-sm text-slate-400">Checking regressions…</p>
                  ) : !regressions.data?.data.length ? (
                    <div className="flex items-center gap-2 text-emerald-700 font-semibold text-sm py-2">
                      <span className="w-2 h-2 rounded-full bg-emerald-500" />
                      <span>✓ Zero regressions detected across candidate model outputs.</span>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {regressions.data.data.map((reg) => (
                        <div key={reg.id} className="p-3.5 border rounded-lg bg-rose-50/50 border-rose-200 flex justify-between items-start">
                          <div>
                            <div className="flex items-center gap-2">
                              <Badge variant={SEVERITY_VARIANTS[reg.severity] || "warning"}>
                                {reg.severity}
                              </Badge>
                              <span className="text-sm font-bold text-slate-900">{reg.metric_name}</span>
                            </div>
                            <p className="text-xs text-slate-600 mt-1">{reg.explanation}</p>
                          </div>
                          <div className="text-xs text-right font-mono text-slate-600">
                            <div>Base: {reg.baseline_value?.toFixed(4)}</div>
                            <div className="font-semibold text-rose-700">Cand: {reg.candidate_value?.toFixed(4)}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </Card>

                {/* Quality Gates Checklist */}
                <Card title="Quality Gate Thresholds" className="shadow-sm">
                  {qualityGates.isLoading ? (
                    <p className="text-sm text-slate-400">Loading quality gates…</p>
                  ) : !qualityGates.data?.data.length ? (
                    <p className="text-xs text-slate-500">No explicit quality gates configured.</p>
                  ) : (
                    <div className="space-y-2">
                      {qualityGates.data.data.map((gate) => (
                        <div key={gate.id} className="flex justify-between items-center py-2.5 px-3.5 border border-slate-100 rounded-lg bg-slate-50">
                          <div>
                            <span className="text-sm font-semibold text-slate-800">{gate.metric_name}</span>
                            <span className="text-xs text-slate-500 font-mono ml-3">Actual: {gate.actual_value !== null ? gate.actual_value.toFixed(4) : "N/A"}</span>
                          </div>
                          <StatusBadge status={gate.status} />
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
      </div>
    </AppShell>
  );
}
