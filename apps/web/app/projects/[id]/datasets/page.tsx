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
import { FormField, Input } from "@/components/ui/Input";
import { StatusBadge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/Table";

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

  const datasetList = datasets.data?.data ?? [];

  return (
    <AppShell>
      <div className="space-y-6" data-testid="datasets-view">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 mb-1">
              <Link href={`/projects/${projectId}`} className="hover:text-slate-900 transition">
                ← Back to Project
              </Link>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Evaluation Datasets & Test Suites
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Version-controlled, immutable golden datasets for automated quality gate runs and regression testing.
            </p>
          </div>
        </div>

        {error ? <Alert kind="error">{error}</Alert> : null}

        {/* Add Dataset Form */}
        <Card title="Create Dataset Container" subtitle="Create a versioned container for test cases" className="shadow-sm">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <FormField label="Dataset Name" htmlFor="dname" required>
              <Input
                id="dname"
                aria-label="Dataset name"
                placeholder="e.g. Customer Support QA Benchmarks"
                value={name}
                onChange={(e) => setName(e.target.value)}
                data-testid="dataset-name-input"
              />
            </FormField>

            <FormField label="Description (optional)" htmlFor="ddesc">
              <Input
                id="ddesc"
                aria-label="Dataset description"
                placeholder="Dataset purpose and domain coverage"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                data-testid="dataset-desc-input"
              />
            </FormField>
          </div>

          <div className="mt-4 flex justify-end">
            <Button
              onClick={() => createMutation.mutate()}
              disabled={createMutation.isPending || !name}
              isLoading={createMutation.isPending}
              data-testid="create-dataset-btn"
            >
              Create Dataset
            </Button>
          </div>
        </Card>

        {/* Dataset Table */}
        <Card title={`Datasets (${datasetList.length})`} className="shadow-sm">
          {datasets.isLoading ? (
            <div className="p-8 text-center text-slate-400">Loading datasets…</div>
          ) : datasetList.length === 0 ? (
            <EmptyState
              title="No datasets created yet"
              description="Create a dataset container above to upload CSV or JSONL test cases."
            />
          ) : (
            <Table>
              <TableHeader>
                <tr>
                  <TableHead>Dataset Name</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Latest Version</TableHead>
                  <TableHead>Total Records</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </tr>
              </TableHeader>
              <TableBody>
                {datasetList.map((d) => (
                  <TableRow key={d.id}>
                    <TableCell className="font-semibold text-slate-900">
                      <Link
                        className="text-brand-600 hover:text-brand-700 hover:underline"
                        href={`/projects/${projectId}/datasets/${d.id}`}
                        data-testid={`dataset-link-${d.id}`}
                      >
                        {d.name}
                      </Link>
                    </TableCell>
                    <TableCell className="text-slate-500 text-xs">{d.description ?? "—"}</TableCell>
                    <TableCell className="font-mono text-xs font-semibold text-slate-700">
                      v{d.latest_version ?? "—"}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-slate-900">{d.record_count}</TableCell>
                    <TableCell>
                      <StatusBadge status={d.status} />
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Link href={`/projects/${projectId}/datasets/${d.id}`}>
                          <Button variant="secondary" size="sm" data-testid={`open-dataset-${d.id}`}>
                            Open & Upload →
                          </Button>
                        </Link>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-rose-600 hover:bg-rose-50"
                          disabled={d.status === "ARCHIVED"}
                          onClick={() => {
                            if (confirm(`Archive dataset ${d.name}?`)) archiveMutation.mutate(d.id);
                          }}
                        >
                          Archive
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Card>
      </div>
    </AppShell>
  );
}
