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
import { FormField, Input, Select } from "@/components/ui/Input";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/Table";

const EVALUATOR_TYPES = [
  "exact_match",
  "case_insensitive_exact_match",
  "contains",
  "regex",
  "json_match",
  "numeric_match",
  "length",
  "llm_judge",
];

export default function EvaluationsPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  // Create-form state.
  const [environmentId, setEnvironmentId] = useState("");
  const [modelId, setModelId] = useState("");
  const [datasetId, setDatasetId] = useState("");
  const [versionId, setVersionId] = useState("");
  const [evaluatorType, setEvaluatorType] = useState("exact_match");
  const [maxConcurrency, setMaxConcurrency] = useState("4");
  const [timeoutSeconds, setTimeoutSeconds] = useState("30");
  const [stopOnError, setStopOnError] = useState(false);
  const [judgeModelId, setJudgeModelId] = useState("");
  const [rubricId, setRubricId] = useState("");
  const [threshold, setThreshold] = useState("0.75");
  const [passPolicy, setPassPolicy] = useState("ALL");

  const evaluations = useQuery({
    queryKey: ["evaluations", projectId],
    queryFn: () => api.listEvaluations(projectId, { page: 1, page_size: 50 }),
    refetchInterval: (query) => {
      const active = query.state.data?.data.some((r) => r.status === "QUEUED" || r.status === "RUNNING");
      return active ? 2000 : false;
    },
  });

  const environments = useQuery({
    queryKey: ["environments", projectId],
    queryFn: () => api.listEnvironments(projectId),
  });
  const models = useQuery({
    queryKey: ["models", projectId],
    queryFn: () => api.listModels(projectId),
  });
  const datasets = useQuery({
    queryKey: ["datasets", projectId],
    queryFn: () => api.listDatasets(projectId, { page: 1, page_size: 50 }),
  });
  const versions = useQuery({
    queryKey: ["dataset-versions", datasetId],
    queryFn: () => api.listDatasetVersions(datasetId, { page: 1, page_size: 50 }),
    enabled: Boolean(datasetId),
  });
  const rubrics = useQuery({
    queryKey: ["rubrics", projectId],
    queryFn: () => api.listRubrics(projectId, { page: 1, page_size: 50 }),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.createEvaluation({
        project_id: projectId,
        environment_id: environmentId || undefined,
        dataset_version_id: versionId,
        model_id: modelId,
        configuration: {
          evaluators: [
            {
              type: evaluatorType,
              enabled: true,
              ...(evaluatorType === "llm_judge"
                ? {
                    judge_model_id: judgeModelId,
                    rubric_id: rubricId,
                    threshold: Number(threshold) || 0.75,
                    reference_required: true,
                  }
                : {}),
            },
          ],
          execution: {
            max_concurrency: Number(maxConcurrency) || 5,
            timeout_seconds: Number(timeoutSeconds) || 30,
            stop_on_error: stopOnError,
            pass_policy: passPolicy as "ANY" | "ALL" | "WEIGHTED",
            ...(passPolicy === "WEIGHTED" ? { threshold: Number(threshold) || 0.75 } : {}),
          },
        },
      }),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["evaluations", projectId] });
    },
    onError: (e) => setError(e instanceof ApiClientError ? e.message : "Failed to create evaluation"),
  });

  const canCreate = Boolean(
    modelId &&
      versionId &&
      (evaluatorType !== "llm_judge" || (judgeModelId && rubricId)),
  );

  const evalList = evaluations.data?.data ?? [];

  return (
    <AppShell>
      <div className="space-y-6" data-testid="evaluations-view">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 mb-1">
              <Link href={`/projects/${projectId}`} className="hover:text-slate-900 transition">
                ← Back to Project
              </Link>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Evaluations & Regression Quality Gates
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Execute test suites against AI models and compare outputs with exact, fuzzy, schema, and LLM-judge scorers.
            </p>
          </div>
        </div>

        {error ? <Alert kind="error">{error}</Alert> : null}

        {/* Run Evaluation Card */}
        <Card
          title="Run Automated Evaluation"
          subtitle="Configure target model, immutable dataset version, and scoring rules"
          className="shadow-sm"
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <FormField label="Target AI Model" htmlFor="emodel" required>
              <Select
                id="emodel"
                value={modelId}
                onChange={(e) => setModelId(e.target.value)}
                data-testid="eval-model-select"
              >
                <option value="">Select a model…</option>
                {(models.data?.data ?? []).map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} ({m.model_identifier})
                  </option>
                ))}
              </Select>
            </FormField>

            <FormField label="Test Dataset" htmlFor="edataset" required>
              <Select
                id="edataset"
                value={datasetId}
                onChange={(e) => {
                  setDatasetId(e.target.value);
                  setVersionId("");
                }}
                data-testid="eval-dataset-select"
              >
                <option value="">Select a dataset…</option>
                {(datasets.data?.data ?? []).map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.record_count} records)
                  </option>
                ))}
              </Select>
            </FormField>

            <FormField label="Dataset Version (Immutable)" htmlFor="eversion" required>
              <Select
                id="eversion"
                value={versionId}
                onChange={(e) => setVersionId(e.target.value)}
                disabled={!datasetId}
                data-testid="eval-version-select"
              >
                <option value="">Select a version…</option>
                {(versions.data?.data ?? []).map((v) => (
                  <option key={v.id} value={v.id}>
                    v{v.version_number} ({v.record_count} records)
                  </option>
                ))}
              </Select>
            </FormField>

            <FormField label="Evaluator Type" htmlFor="etype" required>
              <Select
                id="etype"
                value={evaluatorType}
                onChange={(e) => setEvaluatorType(e.target.value)}
                data-testid="eval-type-select"
              >
                {EVALUATOR_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t.replace(/_/g, " ")}
                  </option>
                ))}
              </Select>
            </FormField>

            <FormField label="Target Environment (Optional)" htmlFor="eenv">
              <Select
                id="eenv"
                value={environmentId}
                onChange={(e) => setEnvironmentId(e.target.value)}
              >
                <option value="">— none (Default) —</option>
                {(environments.data?.data ?? []).map((env) => (
                  <option key={env.id} value={env.id}>
                    {env.name} ({env.environment_type})
                  </option>
                ))}
              </Select>
            </FormField>

            <FormField label="Pass Policy" htmlFor="epolicy">
              <Select
                id="epolicy"
                value={passPolicy}
                onChange={(e) => setPassPolicy(e.target.value)}
              >
                <option value="ALL">ALL (Strict: 100% Pass)</option>
                <option value="ANY">ANY (Tolerant)</option>
                <option value="WEIGHTED">WEIGHTED (Score Threshold)</option>
              </Select>
            </FormField>
          </div>

          {/* LLM Judge Options */}
          {evaluatorType === "llm_judge" && (
            <div className="mt-4 pt-4 border-t border-slate-100 grid grid-cols-1 sm:grid-cols-3 gap-4">
              <FormField label="Judge Model" htmlFor="jmodel" required>
                <Select
                  id="jmodel"
                  value={judgeModelId}
                  onChange={(e) => setJudgeModelId(e.target.value)}
                >
                  <option value="">Select judge model…</option>
                  {(models.data?.data ?? []).map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
                </Select>
              </FormField>

              <FormField label="Rubric" htmlFor="jrubric" required>
                <Select
                  id="jrubric"
                  value={rubricId}
                  onChange={(e) => setRubricId(e.target.value)}
                >
                  <option value="">Select a rubric…</option>
                  {(rubrics.data?.data ?? [])
                    .filter((r) => r.status === "ACTIVE")
                    .map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.name} v{r.version}
                      </option>
                    ))}
                </Select>
              </FormField>

              <FormField label="Score Threshold (0–1)" htmlFor="jthresh">
                <Input
                  id="jthresh"
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={threshold}
                  onChange={(e) => setThreshold(e.target.value)}
                />
              </FormField>
            </div>
          )}

          <div className="mt-5 flex items-center justify-between pt-2 border-t border-slate-100">
            <label className="flex items-center gap-2 text-xs text-slate-600 cursor-pointer">
              <input
                type="checkbox"
                checked={stopOnError}
                onChange={(e) => setStopOnError(e.target.checked)}
                className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
              />
              <span>Fail fast (stop execution on first error)</span>
            </label>

            <Button
              onClick={() => createMutation.mutate()}
              disabled={createMutation.isPending || !canCreate}
              isLoading={createMutation.isPending}
              data-testid="start-evaluation-btn"
            >
              Start Evaluation Run
            </Button>
          </div>
        </Card>

        {/* Evaluation Runs History */}
        <Card title={`Evaluation Runs (${evalList.length})`} className="shadow-sm">
          {evaluations.isLoading ? (
            <div className="p-8 text-center text-slate-400">Loading evaluations…</div>
          ) : evalList.length === 0 ? (
            <EmptyState
              title="No evaluations executed yet"
              description="Configure and launch an evaluation above to benchmark accuracy, latency, and quality gates."
            />
          ) : (
            <Table>
              <TableHeader>
                <tr>
                  <TableHead>Run ID / Status</TableHead>
                  <TableHead>Progress</TableHead>
                  <TableHead>Pass / Fail / Error</TableHead>
                  <TableHead>Execution Time</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </tr>
              </TableHeader>
              <TableBody>
                {evalList.map((r) => {
                  const passPercent =
                    r.total_tests > 0 ? Math.round((r.passed_tests / r.total_tests) * 100) : 0;
                  return (
                    <TableRow key={r.id}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <StatusBadge status={r.status} />
                          <span className="font-mono text-xs text-slate-500">
                            {r.id.slice(0, 8)}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="space-y-1">
                          <div className="flex items-center justify-between text-xs text-slate-600 font-mono">
                            <span>{r.completed_tests}/{r.total_tests}</span>
                            <span>{passPercent}%</span>
                          </div>
                          <div className="h-1.5 w-32 rounded-full bg-slate-100 overflow-hidden">
                            <div
                              className="h-full bg-brand-600 transition-all duration-300"
                              style={{ width: `${r.total_tests ? (r.completed_tests / r.total_tests) * 100 : 0}%` }}
                            />
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2 font-mono text-xs">
                          <span className="text-emerald-700 font-semibold">{r.passed_tests} pass</span>
                          <span className="text-slate-300">/</span>
                          <span className="text-rose-700 font-semibold">{r.failed_tests} fail</span>
                          <span className="text-slate-300">/</span>
                          <span className="text-amber-700">{r.error_tests} err</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-xs font-mono text-slate-600">
                        {r.status === "COMPLETED" ? "Deterministic" : "Active"}
                      </TableCell>
                      <TableCell className="text-xs text-slate-500 font-mono">
                        {new Date(r.created_at).toLocaleString()}
                      </TableCell>
                      <TableCell className="text-right">
                        <Link href={`/projects/${projectId}/evaluations/${r.id}`}>
                          <Button variant="secondary" size="sm" data-testid={`view-eval-${r.id}`}>
                            View Analysis →
                          </Button>
                        </Link>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </Card>
      </div>
    </AppShell>
  );
}
