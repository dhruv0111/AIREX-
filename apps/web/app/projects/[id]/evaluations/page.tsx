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
  // Phase 4 — LLM judge + combined scoring.
  const [judgeModelId, setJudgeModelId] = useState("");
  const [rubricId, setRubricId] = useState("");
  const [threshold, setThreshold] = useState("0.75");
  const [passPolicy, setPassPolicy] = useState("ALL");

  const evaluations = useQuery({
    queryKey: ["evaluations", projectId],
    queryFn: () => api.listEvaluations(projectId, { page: 1, page_size: 50 }),
    refetchInterval: (query) => {
      const active = query.state.data?.data.some((r) => r.status === "QUEUED" || r.status === "RUNNING");
      return active ? 3000 : false;
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
      setEnvironmentId("");
      setModelId("");
      setDatasetId("");
      setVersionId("");
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

  return (
    <AppShell>
      <Link href={`/projects/${projectId}`} className="text-sm text-brand hover:underline">
        ← Project
      </Link>
      <h1 className="mt-2 mb-6 text-2xl font-bold text-slate-900">Evaluations</h1>
      {error ? <Alert kind="error" className="mb-4">{error}</Alert> : null}

      <Card title="Run an evaluation" className="mb-6">
        <div className="grid gap-3 md:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm text-slate-600">
            Environment (optional)
            <select
              value={environmentId}
              onChange={(e) => setEnvironmentId(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-2"
            >
              <option value="">— none —</option>
              {(environments.data?.data ?? []).map((env) => (
                <option key={env.id} value={env.id}>
                  {env.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm text-slate-600">
            Model
            <select
              value={modelId}
              onChange={(e) => setModelId(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-2"
            >
              <option value="">Select a model…</option>
              {(models.data?.data ?? []).map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm text-slate-600">
            Dataset
            <select
              value={datasetId}
              onChange={(e) => {
                setDatasetId(e.target.value);
                setVersionId("");
              }}
              className="rounded-md border border-slate-300 px-3 py-2"
            >
              <option value="">Select a dataset…</option>
              {(datasets.data?.data ?? []).map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm text-slate-600">
            Dataset version (immutable)
            <select
              value={versionId}
              onChange={(e) => setVersionId(e.target.value)}
              disabled={!datasetId}
              className="rounded-md border border-slate-300 px-3 py-2 disabled:bg-slate-50"
            >
              <option value="">Select a version…</option>
              {(versions.data?.data ?? []).map((v) => (
                <option key={v.id} value={v.id}>
                  v{v.version_number} ({v.record_count} records)
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm text-slate-600">
            Evaluator
            <select
              value={evaluatorType}
              onChange={(e) => setEvaluatorType(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-2"
            >
              {EVALUATOR_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          {evaluatorType === "llm_judge" ? (
            <>
              <label className="flex flex-col gap-1 text-sm text-slate-600">
                Judge model
                <select
                  value={judgeModelId}
                  onChange={(e) => setJudgeModelId(e.target.value)}
                  className="rounded-md border border-slate-300 px-3 py-2"
                >
                  <option value="">Select a judge model…</option>
                  {(models.data?.data ?? []).map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-sm text-slate-600">
                Rubric
                <select
                  value={rubricId}
                  onChange={(e) => setRubricId(e.target.value)}
                  className="rounded-md border border-slate-300 px-3 py-2"
                >
                  <option value="">Select a rubric…</option>
                  {(rubrics.data?.data ?? [])
                    .filter((r) => r.status === "ACTIVE")
                    .map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.name} v{r.version}
                      </option>
                    ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-sm text-slate-600">
                Threshold (0–1)
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={threshold}
                  onChange={(e) => setThreshold(e.target.value)}
                  className="rounded-md border border-slate-300 px-3 py-2"
                />
              </label>
            </>
          ) : null}
          <label className="flex flex-col gap-1 text-sm text-slate-600">
            Pass policy
            <select
              value={passPolicy}
              onChange={(e) => setPassPolicy(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-2"
            >
              <option value="ALL">ALL</option>
              <option value="ANY">ANY</option>
              <option value="WEIGHTED">WEIGHTED</option>
            </select>
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1 text-sm text-slate-600">
              Max concurrency
              <input
                type="number"
                min={1}
                max={50}
                value={maxConcurrency}
                onChange={(e) => setMaxConcurrency(e.target.value)}
                className="rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm text-slate-600">
              Timeout (s)
              <input
                type="number"
                min={1}
                max={600}
                value={timeoutSeconds}
                onChange={(e) => setTimeoutSeconds(e.target.value)}
                className="rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={stopOnError}
              onChange={(e) => setStopOnError(e.target.checked)}
            />
            Stop on first error
          </label>
        </div>
        <div className="mt-4">
          <Button
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending || !canCreate}
          >
            {createMutation.isPending ? "Creating…" : "Run evaluation"}
          </Button>
        </div>
      </Card>

      {evaluations.isLoading ? (
        <Card><p className="text-sm text-slate-400">Loading evaluations…</p></Card>
      ) : evaluations.isError ? (
        <Card><Alert kind="error">{(evaluations.error as Error).message}</Alert></Card>
      ) : !evaluations.data?.data.length ? (
        <Card><p className="text-sm text-slate-500">No evaluations yet.</p></Card>
      ) : (
        <Card>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-slate-500">
                <th className="py-2 pr-4">Status</th>
                <th className="py-2 pr-4">Progress</th>
                <th className="py-2 pr-4">Pass / Fail / Error</th>
                <th className="py-2 pr-4">Created</th>
                <th className="py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {evaluations.data.data.map((r) => (
                <tr key={r.id} className="border-b">
                  <td className="py-2 pr-4">
                    <span
                      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                        r.status === "COMPLETED"
                          ? "bg-green-100 text-green-700"
                          : r.status === "FAILED"
                            ? "bg-red-100 text-red-700"
                            : "bg-slate-100 text-slate-700"
                      }`}
                    >
                      {r.status}
                    </span>
                  </td>
                  <td className="py-2 pr-4 text-slate-600">
                    {r.completed_tests}/{r.total_tests}
                  </td>
                  <td className="py-2 pr-4 text-slate-600">
                    {r.passed_tests} / {r.failed_tests} / {r.error_tests}
                  </td>
                  <td className="py-2 pr-4 text-slate-500">
                    {new Date(r.created_at).toLocaleString()}
                  </td>
                  <td className="py-2">
                    <Link href={`/projects/${projectId}/evaluations/${r.id}`}>
                      <Button variant="secondary">View</Button>
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </AppShell>
  );
}
