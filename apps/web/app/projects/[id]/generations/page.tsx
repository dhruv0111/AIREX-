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

const GENERATION_TYPES = ["BASIC", "EDGE_CASE", "BOUNDARY", "NEGATIVE", "AMBIGUOUS", "ADVERSARIAL"];
const SOURCE_TYPES = ["MANUAL_INSTRUCTION", "DATASET", "TEST_CASES", "EVALUATION_FAILURES"];

const STATUS_STYLES: Record<string, string> = {
  QUEUED: "bg-slate-100 text-slate-600",
  RUNNING: "bg-blue-100 text-blue-700",
  COMPLETED: "bg-green-100 text-green-700",
  FAILED: "bg-red-100 text-red-700",
  CANCELLED: "bg-slate-100 text-slate-500",
};

export default function GenerationsPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const [sourceType, setSourceType] = useState("MANUAL_INSTRUCTION");
  const [generationType, setGenerationType] = useState("BASIC");
  const [count, setCount] = useState("20");
  const [instruction, setInstruction] = useState("");
  const [generatorModelId, setGeneratorModelId] = useState("");
  const [environmentId, setEnvironmentId] = useState("");
  const [datasetId, setDatasetId] = useState("");
  const [datasetVersionId, setDatasetVersionId] = useState("");

  const generations = useQuery({
    queryKey: ["generations", projectId],
    queryFn: () => api.listGenerations(projectId, { page: 1, page_size: 50 }),
    refetchInterval: (query) =>
      query.state.data?.data.some((g) => g.status === "QUEUED" || g.status === "RUNNING")
        ? 3000
        : false,
  });
  const models = useQuery({
    queryKey: ["models", projectId],
    queryFn: () => api.listModels(projectId),
  });
  const environments = useQuery({
    queryKey: ["environments", projectId],
    queryFn: () => api.listEnvironments(projectId),
  });
  const datasets = useQuery({
    queryKey: ["datasets", projectId],
    queryFn: () => api.listDatasets(projectId, { page: 1, page_size: 50 }),
  });
  const versions = useQuery({
    queryKey: ["dataset-versions", datasetId],
    queryFn: () => api.listDatasetVersions(datasetId, { page: 1, page_size: 50 }),
    enabled: !!datasetId,
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.createGeneration({
        project_id: projectId,
        environment_id: environmentId || undefined,
        source_type: sourceType,
        source_reference:
          sourceType === "DATASET" && datasetVersionId
            ? { dataset_version_id: datasetVersionId }
            : undefined,
        generation_type: generationType,
        instruction: instruction || undefined,
        count: Number(count) || 20,
        configuration: { generation_types: [generationType] },
        generator_model_id: generatorModelId,
      }),
    onSuccess: () => {
      setInstruction("");
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["generations", projectId] });
    },
    onError: (e) =>
      setError(e instanceof ApiClientError ? e.message : "Failed to start generation"),
  });

  const cancelMutation = useMutation({
    mutationFn: (id: string) => api.cancelGeneration(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["generations", projectId] }),
    onError: (e) => setError(e instanceof ApiClientError ? e.message : "Failed to cancel"),
  });

  const canCreate =
    !!generatorModelId && Number(count) >= 1 && Number(count) <= 100 &&
    (sourceType !== "DATASET" || !!datasetVersionId);

  return (
    <AppShell>
      <Link href={`/projects/${projectId}`} className="text-sm text-brand hover:underline">
        ← Project
      </Link>
      <h1 className="mt-2 mb-6 text-2xl font-bold text-slate-900">Test Generation</h1>
      {error ? <Alert kind="error" className="mb-4">{error}</Alert> : null}

      <Card title="Generate test cases" className="mb-6">
        <div className="grid gap-3 md:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm text-slate-600">
            Source
            <select
              value={sourceType}
              onChange={(e) => {
                setSourceType(e.target.value);
                setDatasetVersionId("");
              }}
              className="rounded-md border border-slate-300 px-3 py-2"
            >
              {SOURCE_TYPES.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm text-slate-600">
            Generation type
            <select
              value={generationType}
              onChange={(e) => setGenerationType(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-2"
            >
              {GENERATION_TYPES.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm text-slate-600">
            Generator model
            <select
              value={generatorModelId}
              onChange={(e) => setGeneratorModelId(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-2"
            >
              <option value="">Select a model…</option>
              {(models.data?.data ?? []).map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} ({m.model_identifier})
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm text-slate-600">
            Count (1–100)
            <input
              type="number"
              min={1}
              max={100}
              value={count}
              onChange={(e) => setCount(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-2"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm text-slate-600">
            Environment (optional)
            <select
              value={environmentId}
              onChange={(e) => setEnvironmentId(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-2"
            >
              <option value="">None</option>
              {(environments.data?.data ?? []).map((env) => (
                <option key={env.id} value={env.id}>{env.name}</option>
              ))}
            </select>
          </label>
          {sourceType === "DATASET" ? (
            <label className="flex flex-col gap-1 text-sm text-slate-600">
              Dataset version
              <select
                value={datasetVersionId}
                onChange={(e) => setDatasetVersionId(e.target.value)}
                className="rounded-md border border-slate-300 px-3 py-2"
              >
                <option value="">Select a dataset…</option>
                {(datasets.data?.data ?? []).map((d) => (
                  <option key={d.id} value={d.id} disabled>
                    {d.name}
                  </option>
                ))}
                {datasetId && (versions.data?.data ?? []).map((v) => (
                  <option key={v.id} value={v.id}>
                    {datasetId.slice(0, 8)}… v{v.version_number}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <label className="flex flex-col gap-1 text-sm text-slate-600">
              Instruction
              <input
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                placeholder="Describe the use case to generate tests for"
                className="rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
          )}
        </div>
        <div className="mt-4">
          <Button
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending || !canCreate}
          >
            {createMutation.isPending ? "Queuing…" : "Generate test cases"}
          </Button>
        </div>
      </Card>

      {generations.isLoading ? (
        <Card><p className="text-sm text-slate-400">Loading generations…</p></Card>
      ) : generations.isError ? (
        <Card><Alert kind="error">{(generations.error as Error).message}</Alert></Card>
      ) : !generations.data?.data.length ? (
        <Card><p className="text-sm text-slate-500">No generations yet.</p></Card>
      ) : (
        <Card>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-slate-500">
                <th className="py-2 pr-4">Type</th>
                <th className="py-2 pr-4">Source</th>
                <th className="py-2 pr-4">Status</th>
                <th className="py-2 pr-4">Count</th>
                <th className="py-2 pr-4">Candidates</th>
                <th className="py-2 pr-4">Created</th>
                <th className="py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {generations.data.data.map((g) => (
                <tr key={g.id} className="border-b">
                  <td className="py-2 pr-4 font-medium text-slate-900">
                    <Link href={`/projects/${projectId}/generations/${g.id}`} className="hover:underline">
                      {g.generation_type}
                    </Link>
                  </td>
                  <td className="py-2 pr-4 text-slate-600">{g.source_type}</td>
                  <td className="py-2 pr-4">
                    <span
                      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                        STATUS_STYLES[g.status] ?? "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {g.status}
                    </span>
                  </td>
                  <td className="py-2 pr-4">{g.count}</td>
                  <td className="py-2 pr-4 text-slate-600">{g.candidate_count}</td>
                  <td className="py-2 pr-4 text-slate-500">{new Date(g.created_at).toLocaleString()}</td>
                  <td className="py-2">
                    {g.status === "QUEUED" || g.status === "RUNNING" ? (
                      <Button
                        variant="danger"
                        onClick={() => cancelMutation.mutate(g.id)}
                      >
                        Cancel
                      </Button>
                    ) : null}
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
