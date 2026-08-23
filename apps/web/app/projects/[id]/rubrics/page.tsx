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

interface CriterionRow {
  name: string;
  description: string;
  weight: string;
}

export default function RubricsPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [rows, setRows] = useState<CriterionRow[]>([
    { name: "", description: "", weight: "1" },
  ]);

  const rubrics = useQuery({
    queryKey: ["rubrics", projectId],
    queryFn: () => api.listRubrics(projectId, { page: 1, page_size: 50 }),
  });

  const totalWeight = rows.reduce((sum, r) => sum + (Number(r.weight) || 0), 0);

  const createMutation = useMutation({
    mutationFn: () =>
      api.createRubric({
        project_id: projectId,
        name,
        description: description || undefined,
        criteria: rows.map((r) => ({
          name: r.name,
          description: r.description,
          weight: Number(r.weight) || 0,
        })),
      }),
    onSuccess: () => {
      setName("");
      setDescription("");
      setRows([{ name: "", description: "", weight: "1" }]);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["rubrics", projectId] });
    },
    onError: (e) => setError(e instanceof ApiClientError ? e.message : "Failed to create rubric"),
  });

  const archiveMutation = useMutation({
    mutationFn: (id: string) => api.archiveRubric(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["rubrics", projectId] }),
    onError: (e) => setError(e instanceof ApiClientError ? e.message : "Failed to archive rubric"),
  });

  const setRow = (index: number, field: keyof CriterionRow, value: string) => {
    setRows((prev) => prev.map((r, i) => (i === index ? { ...r, [field]: value } : r)));
  };

  const valid = name.trim().length > 0 && rows.every((r) => r.name.trim() && r.weight !== "");

  return (
    <AppShell>
      <Link href={`/projects/${projectId}`} className="text-sm text-brand hover:underline">
        ← Project
      </Link>
      <h1 className="mt-2 mb-6 text-2xl font-bold text-slate-900">Rubrics</h1>
      {error ? <Alert kind="error" className="mb-4">{error}</Alert> : null}

      <Card title="Create rubric" className="mb-6">
        <div className="flex flex-col gap-3 md:flex-row">
          <input
            aria-label="Rubric name"
            placeholder="Name (e.g. Answer Quality)"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="flex-1 rounded-md border border-slate-300 px-3 py-2"
          />
          <input
            aria-label="Rubric description"
            placeholder="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="flex-1 rounded-md border border-slate-300 px-3 py-2"
          />
        </div>
        <div className="mt-4 space-y-2">
          {rows.map((row, i) => (
            <div key={i} className="flex flex-col gap-2 md:flex-row">
              <input
                aria-label="Criterion name"
                placeholder="Criterion (e.g. correctness)"
                value={row.name}
                onChange={(e) => setRow(i, "name", e.target.value)}
                className="flex-1 rounded-md border border-slate-300 px-3 py-2"
              />
              <input
                aria-label="Criterion description"
                placeholder="Description"
                value={row.description}
                onChange={(e) => setRow(i, "description", e.target.value)}
                className="flex-[2] rounded-md border border-slate-300 px-3 py-2"
              />
              <input
                aria-label="Criterion weight"
                placeholder="Weight"
                type="number"
                min={0}
                value={row.weight}
                onChange={(e) => setRow(i, "weight", e.target.value)}
                className="w-24 rounded-md border border-slate-300 px-3 py-2"
              />
              <Button
                variant="danger"
                onClick={() => setRows((prev) => prev.filter((_, idx) => idx !== i))}
                disabled={rows.length === 1}
              >
                Remove
              </Button>
            </div>
          ))}
          <Button variant="secondary" onClick={() => setRows((prev) => [...prev, { name: "", description: "", weight: "1" }])}>
            Add criterion
          </Button>
        </div>
        <div className="mt-4 flex items-center gap-3">
          <Button
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending || !valid}
          >
            {createMutation.isPending ? "Creating…" : "Create rubric"}
          </Button>
          <span className="text-sm text-slate-500">
            Total weight: {totalWeight.toFixed(2)} (weights are normalized to 1.0)
          </span>
        </div>
      </Card>

      {rubrics.isLoading ? (
        <Card><p className="text-sm text-slate-400">Loading rubrics…</p></Card>
      ) : rubrics.isError ? (
        <Card><Alert kind="error">{(rubrics.error as Error).message}</Alert></Card>
      ) : !rubrics.data?.data.length ? (
        <Card><p className="text-sm text-slate-500">No rubrics yet.</p></Card>
      ) : (
        <Card>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-slate-500">
                <th className="py-2 pr-4">Name</th>
                <th className="py-2 pr-4">Version</th>
                <th className="py-2 pr-4">Criteria</th>
                <th className="py-2 pr-4">Status</th>
                <th className="py-2 pr-4">Created</th>
                <th className="py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rubrics.data.data.map((r) => (
                <tr key={r.id} className="border-b">
                  <td className="py-2 pr-4 font-medium text-slate-900">{r.name}</td>
                  <td className="py-2 pr-4">v{r.version}</td>
                  <td className="py-2 pr-4 text-slate-600">
                    {r.criteria.map((c) => c.name).join(", ")}
                  </td>
                  <td className="py-2 pr-4">
                    <span
                      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                        r.status === "ACTIVE"
                          ? "bg-green-100 text-green-700"
                          : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {r.status}
                    </span>
                  </td>
                  <td className="py-2 pr-4 text-slate-500">
                    {new Date(r.created_at).toLocaleString()}
                  </td>
                  <td className="py-2">
                    <Button
                      variant="danger"
                      disabled={r.status === "ARCHIVED"}
                      onClick={() => {
                        if (confirm(`Archive rubric ${r.name} v${r.version}?`)) {
                          archiveMutation.mutate(r.id);
                        }
                      }}
                    >
                      Archive
                    </Button>
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
