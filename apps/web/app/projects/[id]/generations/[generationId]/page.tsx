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

const CANDIDATE_STYLES: Record<string, string> = {
  PENDING_REVIEW: "bg-amber-100 text-amber-700",
  APPROVED: "bg-green-100 text-green-700",
  REJECTED: "bg-red-100 text-red-700",
};

export default function GenerationDetailPage() {
  const params = useParams<{ id: string; generationId: string }>();
  const projectId = params.id;
  const generationId = params.generationId;
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [datasetId, setDatasetId] = useState("");

  const generation = useQuery({
    queryKey: ["generation", generationId],
    queryFn: () => api.getGeneration(generationId),
    refetchInterval: (query) =>
      query.state.data?.data.status === "QUEUED" || query.state.data?.data.status === "RUNNING"
        ? 3000
        : false,
  });
  const candidates = useQuery({
    queryKey: ["candidates", generationId],
    queryFn: () => api.listCandidates(generationId, { page: 1, page_size: 100 }),
    refetchInterval: (query) =>
      query.state.data?.data.some((c) => c.status === "PENDING_REVIEW") ? 3000 : false,
  });
  const datasets = useQuery({
    queryKey: ["datasets", projectId],
    queryFn: () => api.listDatasets(projectId, { page: 1, page_size: 50 }),
  });

  const reviewMutation = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "approve" | "reject" }) =>
      api.reviewCandidate(id, action),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["candidates", generationId] });
      queryClient.invalidateQueries({ queryKey: ["generation", generationId] });
    },
    onError: (e) => setError(e instanceof ApiClientError ? e.message : "Review failed"),
  });

  const datasetMutation = useMutation({
    mutationFn: (candidateIds: string[]) =>
      api.createDatasetVersionFromCandidates(generationId, { dataset_id: datasetId, candidate_ids: candidateIds }),
    onSuccess: () => {
      setError("Dataset version created from approved candidates.");
      queryClient.invalidateQueries({ queryKey: ["candidates", generationId] });
      queryClient.invalidateQueries({ queryKey: ["generation", generationId] });
      queryClient.invalidateQueries({ queryKey: ["datasets", projectId] });
    },
    onError: (e) => setError(e instanceof ApiClientError ? e.message : "Dataset creation failed"),
  });

  const approved = (candidates.data?.data ?? []).filter((c) => c.status === "APPROVED");
  const data = generation.data?.data;

  return (
    <AppShell>
      <Link href={`/projects/${projectId}/generations`} className="text-sm text-brand hover:underline">
        ← Generations
      </Link>
      <h1 className="mt-2 mb-6 text-2xl font-bold text-slate-900">
        Generation · {data?.generation_type ?? "…"}
      </h1>
      {error ? <Alert kind="error" className="mb-4">{error}</Alert> : null}

      {generation.isLoading ? (
        <Card><p className="text-sm text-slate-400">Loading generation…</p></Card>
      ) : generation.isError ? (
        <Card><Alert kind="error">{(generation.error as Error).message}</Alert></Card>
      ) : data ? (
        <>
          <Card title="Summary" className="mb-6">
            <dl className="grid grid-cols-2 gap-3 text-sm md:grid-cols-3">
              <div>
                <dt className="text-slate-500">Status</dt>
                <dd className="font-medium text-slate-900">{data.status}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Source</dt>
                <dd className="text-slate-800">{data.source_type}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Type</dt>
                <dd className="text-slate-800">{data.generation_type}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Requested</dt>
                <dd className="text-slate-800">{data.count}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Candidates</dt>
                <dd className="text-slate-800">
                  {data.candidate_count} ({data.approved_count} approved · {data.rejected_count} rejected)
                </dd>
              </div>
              <div>
                <dt className="text-slate-500">Prompt version</dt>
                <dd className="text-slate-800">{data.prompt_version ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Instruction</dt>
                <dd className="text-slate-800">{data.instruction ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Created</dt>
                <dd className="text-slate-800">{new Date(data.created_at).toLocaleString()}</dd>
              </div>
            </dl>
          </Card>

          <Card title="Candidates" className="mb-6">
            {candidates.isLoading ? (
              <p className="text-sm text-slate-400">Loading candidates…</p>
            ) : candidates.isError ? (
              <Alert kind="error">{(candidates.error as Error).message}</Alert>
            ) : !candidates.data?.data.length ? (
              <p className="text-sm text-slate-500">
                {data.status === "FAILED"
                  ? "This generation failed before producing candidates."
                  : "No candidates yet."}
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-slate-500">
                      <th className="py-2 pr-4">Input</th>
                      <th className="py-2 pr-4">Expected</th>
                      <th className="py-2 pr-4">Category</th>
                      <th className="py-2 pr-4">Difficulty</th>
                      <th className="py-2 pr-4">Quality</th>
                      <th className="py-2 pr-4">Status</th>
                      <th className="py-2">Review</th>
                    </tr>
                  </thead>
                  <tbody>
                    {candidates.data.data.map((c) => (
                      <tr key={c.id} className="border-b align-top">
                        <td className="max-w-xs py-2 pr-4 text-slate-800">{c.input}</td>
                        <td className="max-w-xs py-2 pr-4 text-slate-600">
                          {c.expected_output ?? "—"}
                          {c.duplicate_of ? (
                            <span className="ml-1 rounded bg-slate-100 px-1 text-xs text-slate-500">
                              duplicate
                            </span>
                          ) : null}
                        </td>
                        <td className="py-2 pr-4 text-slate-600">{c.category ?? "—"}</td>
                        <td className="py-2 pr-4 text-slate-600">{c.difficulty ?? "—"}</td>
                        <td className="py-2 pr-4 text-slate-600">
                          {c.quality_score != null ? c.quality_score.toFixed(2) : "—"}
                        </td>
                        <td className="py-2 pr-4">
                          <span
                            className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                              CANDIDATE_STYLES[c.status] ?? "bg-slate-100 text-slate-600"
                            }`}
                          >
                            {c.status}
                          </span>
                        </td>
                        <td className="py-2">
                          {c.status === "PENDING_REVIEW" ? (
                            <div className="flex gap-2">
                              <Button
                                onClick={() => reviewMutation.mutate({ id: c.id, action: "approve" })}
                              >
                                Approve
                              </Button>
                              <Button
                                variant="danger"
                                onClick={() => reviewMutation.mutate({ id: c.id, action: "reject" })}
                              >
                                Reject
                              </Button>
                            </div>
                          ) : (
                            <span className="text-xs text-slate-400">{c.dataset_version_id ? "consumed" : "—"}</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <Card title="Add approved candidates to a dataset">
            <div className="flex flex-col gap-3 md:flex-row md:items-end">
              <label className="flex flex-1 flex-col gap-1 text-sm text-slate-600">
                Dataset
                <select
                  value={datasetId}
                  onChange={(e) => setDatasetId(e.target.value)}
                  className="rounded-md border border-slate-300 px-3 py-2"
                >
                  <option value="">Select a dataset…</option>
                  {(datasets.data?.data ?? []).map((d) => (
                    <option key={d.id} value={d.id}>{d.name}</option>
                  ))}
                </select>
              </label>
              <Button
                onClick={() => datasetMutation.mutate(approved.map((c) => c.id))}
                disabled={datasetMutation.isPending || !datasetId || approved.length === 0}
              >
                {datasetMutation.isPending
                  ? "Creating version…"
                  : `Create dataset version (${approved.length} approved)`}
              </Button>
            </div>
            {approved.length === 0 ? (
              <p className="mt-2 text-xs text-slate-400">
                Approve at least one candidate first — generated candidates are never added automatically.
              </p>
            ) : null}
          </Card>
        </>
      ) : null}
    </AppShell>
  );
}
