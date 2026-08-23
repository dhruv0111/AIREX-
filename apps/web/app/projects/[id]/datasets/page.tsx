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

export default function DatasetsPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  const datasets = useQuery({
    queryKey: ["datasets", projectId],
    queryFn: () => api.listDatasets(projectId, { page: 1, page_size: 50 }),
  });

  const createMutation = useMutation({
    mutationFn: () => api.createDataset(projectId, { name, description: description || undefined }),
    onSuccess: () => {
      setName("");
      setDescription("");
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["datasets", projectId] });
    },
    onError: (e) => setError(e instanceof ApiClientError ? e.message : "Failed to create dataset"),
  });

  const archiveMutation = useMutation({
    mutationFn: (id: string) => api.archiveDataset(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["datasets", projectId] }),
    onError: (e) => setError(e instanceof ApiClientError ? e.message : "Failed to archive dataset"),
  });

  return (
    <AppShell>
      <h1 className="mb-6 text-2xl font-bold text-slate-900">Datasets</h1>
      {error ? <Alert kind="error" className="mb-4">{error}</Alert> : null}

      <Card title="Add dataset" className="mb-6">
        <div className="flex flex-col gap-3 md:flex-row">
          <input
            aria-label="Dataset name"
            placeholder="Name (e.g. Customer Support Dataset)"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="flex-1 rounded-md border border-slate-300 px-3 py-2"
          />
          <input
            aria-label="Dataset description"
            placeholder="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="flex-1 rounded-md border border-slate-300 px-3 py-2"
          />
          <Button onClick={() => createMutation.mutate()} disabled={createMutation.isPending || !name}>
            Create dataset
          </Button>
        </div>
      </Card>

      {datasets.isLoading ? (
        <Card><p className="text-sm text-slate-400">Loading datasets…</p></Card>
      ) : datasets.isError ? (
        <Card><Alert kind="error">{(datasets.error as Error).message}</Alert></Card>
      ) : !datasets.data?.data.length ? (
        <Card><p className="text-sm text-slate-500">No datasets yet. Create one above.</p></Card>
      ) : (
        <Card>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-slate-500">
                <th className="py-2 pr-4">Name</th>
                <th className="py-2 pr-4">Description</th>
                <th className="py-2 pr-4">Latest</th>
                <th className="py-2 pr-4">Records</th>
                <th className="py-2 pr-4">Status</th>
                <th className="py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {datasets.data.data.map((d) => (
                <tr key={d.id} className="border-b">
                  <td className="py-2 pr-4 font-medium text-slate-900">
                    <Link className="text-blue-600 hover:underline" href={`/projects/${projectId}/datasets/${d.id}`}>
                      {d.name}
                    </Link>
                  </td>
                  <td className="py-2 pr-4 text-slate-500">{d.description ?? "—"}</td>
                  <td className="py-2 pr-4">v{d.latest_version ?? "—"}</td>
                  <td className="py-2 pr-4">{d.record_count}</td>
                  <td className="py-2 pr-4">{d.status}</td>
                  <td className="py-2">
                    <div className="flex gap-2">
                      <Link href={`/projects/${projectId}/datasets/${d.id}`}>
                        <Button variant="secondary">Open</Button>
                      </Link>
                      <Button
                        variant="danger"
                        disabled={d.status === "ARCHIVED"}
                        onClick={() => {
                          if (confirm(`Archive dataset ${d.name}?`)) archiveMutation.mutate(d.id);
                        }}
                      >
                        Archive
                      </Button>
                    </div>
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
