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
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/Table";

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
    { name: "correctness", description: "Answer correctly answers the user inquiry with factual accuracy", weight: "1" },
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
  const rubricList = rubrics.data?.data ?? [];

  return (
    <AppShell>
      <div className="space-y-6" data-testid="rubrics-view">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 mb-1">
              <Link href={`/projects/${projectId}`} className="hover:text-slate-900 transition">
                ← Back to Project
              </Link>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Evaluation Rubrics & Scoring Criteria
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Define multi-criterion scoring rubrics for LLM judges, weighted composite metrics, and QA grading.
            </p>
          </div>
        </div>

        {error ? <Alert kind="error">{error}</Alert> : null}

        {/* Create Rubric Card */}
        <Card
          title="Create Scoring Rubric"
          subtitle="Configure weighted evaluation dimensions for LLM-as-a-judge scorers"
          className="shadow-sm"
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-5">
            <FormField label="Rubric Name" htmlFor="rname" required>
              <Input
                id="rname"
                aria-label="Rubric name"
                placeholder="e.g. Factual Correctness & Conciseness"
                value={name}
                onChange={(e) => setName(e.target.value)}
                data-testid="rubric-name-input"
              />
            </FormField>

            <FormField label="Description (optional)" htmlFor="rdesc">
              <Input
                id="rdesc"
                aria-label="Rubric description"
                placeholder="Overall criteria description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                data-testid="rubric-desc-input"
              />
            </FormField>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between pb-1 border-b border-slate-100">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Evaluation Criteria
              </span>
              <span className="text-xs text-slate-500">
                Total weight: <strong className="text-slate-900 font-mono">{totalWeight.toFixed(2)}</strong> (normalized to 1.0)
              </span>
            </div>

            {rows.map((row, i) => (
              <div key={i} className="flex flex-col sm:flex-row items-center gap-3 p-3 rounded-lg bg-slate-50 border border-slate-200">
                <Input
                  aria-label="Criterion name"
                  placeholder="Criterion (e.g. correctness)"
                  value={row.name}
                  onChange={(e) => setRow(i, "name", e.target.value)}
                  className="sm:w-1/4"
                  data-testid={`criterion-name-${i}`}
                />
                <Input
                  aria-label="Criterion description"
                  placeholder="Grading instruction (e.g. factual alignment with ground truth)"
                  value={row.description}
                  onChange={(e) => setRow(i, "description", e.target.value)}
                  className="sm:flex-1"
                  data-testid={`criterion-desc-${i}`}
                />
                <div className="flex items-center gap-2 w-full sm:w-auto">
                  <Input
                    aria-label="Criterion weight"
                    placeholder="Weight"
                    type="number"
                    min={0}
                    value={row.weight}
                    onChange={(e) => setRow(i, "weight", e.target.value)}
                    className="w-20 font-mono"
                    data-testid={`criterion-weight-${i}`}
                  />
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-rose-600 hover:bg-rose-50"
                    onClick={() => setRows((prev) => prev.filter((_, idx) => idx !== i))}
                    disabled={rows.length === 1}
                  >
                    ✕
                  </Button>
                </div>
              </div>
            ))}

            <Button
              variant="secondary"
              size="sm"
              onClick={() => setRows((prev) => [...prev, { name: "", description: "", weight: "1" }])}
            >
              + Add Dimension
            </Button>
          </div>

          <div className="mt-6 flex justify-end">
            <Button
              onClick={() => createMutation.mutate()}
              disabled={createMutation.isPending || !valid}
              isLoading={createMutation.isPending}
              data-testid="create-rubric-submit"
            >
              Create Rubric
            </Button>
          </div>
        </Card>

        {/* Rubrics List Table */}
        <Card title={`Configured Rubrics (${rubricList.length})`} className="shadow-sm">
          {rubrics.isLoading ? (
            <div className="p-8 text-center text-slate-400">Loading rubrics…</div>
          ) : rubricList.length === 0 ? (
            <EmptyState
              title="No rubrics created yet"
              description="Create your first scoring rubric above to enable LLM-as-a-judge evaluations."
            />
          ) : (
            <Table>
              <TableHeader>
                <tr>
                  <TableHead>Rubric Name</TableHead>
                  <TableHead>Version</TableHead>
                  <TableHead>Criteria Dimensions</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </tr>
              </TableHeader>
              <TableBody>
                {rubricList.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="font-semibold text-slate-900">{r.name}</TableCell>
                    <TableCell className="font-mono text-xs font-semibold text-slate-600">
                      v{r.version}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1.5">
                        {r.criteria.map((c, idx) => (
                          <span
                            key={idx}
                            className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-slate-100 text-slate-700 border border-slate-200"
                          >
                            {c.name} ({c.weight})
                          </span>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={r.status} />
                    </TableCell>
                    <TableCell className="text-xs text-slate-500 font-mono">
                      {new Date(r.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-rose-600 hover:bg-rose-50"
                        disabled={r.status === "ARCHIVED"}
                        onClick={() => {
                          if (confirm(`Archive rubric ${r.name} v${r.version}?`)) {
                            archiveMutation.mutate(r.id);
                          }
                        }}
                      >
                        Archive
                      </Button>
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
