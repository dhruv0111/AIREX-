"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/Table";

export default function ExperimentsPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;

  const experiments = useQuery({
    queryKey: ["experiments", projectId],
    queryFn: () => api.listExperiments(projectId),
    refetchInterval: (query) =>
      query.state.data?.data.some((e) => e.status === "QUEUED" || e.status === "RUNNING")
        ? 3000
        : false,
  });

  const experimentList = experiments.data?.data ?? [];

  return (
    <AppShell>
      <div className="space-y-6" data-testid="experiments-view">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 mb-1">
              <Link href={`/projects/${projectId}`} className="hover:text-slate-900 transition">
                ← Back to Project
              </Link>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              A/B Experiments & Model Comparisons
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Statistically compare candidate LLMs against baseline versions with automated regression detection and p-value validation.
            </p>
          </div>

          <Link href={`/projects/${projectId}/experiments/new`}>
            <Button data-testid="new-experiment-btn">+ Create Experiment</Button>
          </Link>
        </div>

        {experiments.isError ? (
          <Alert kind="error">{(experiments.error as Error).message}</Alert>
        ) : null}

        {/* Experiments Table */}
        <Card title={`Experiments & Benchmarks (${experimentList.length})`} className="shadow-sm">
          {experiments.isLoading ? (
            <div className="p-8 text-center text-slate-400">Loading experiments…</div>
          ) : experimentList.length === 0 ? (
            <EmptyState
              title="No experiments configured yet"
              description="Create an experiment to run side-by-side A/B comparisons between candidate and baseline LLM models."
              action={
                <Link href={`/projects/${projectId}/experiments/new`}>
                  <Button data-testid="create-first-experiment-btn">+ Create First Experiment</Button>
                </Link>
              }
            />
          ) : (
            <Table>
              <TableHeader>
                <tr>
                  <TableHead>Experiment Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Status / Quality Gate</TableHead>
                  <TableHead>Baseline Model</TableHead>
                  <TableHead>Candidate Model</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </tr>
              </TableHeader>
              <TableBody>
                {experimentList.map((e) => (
                  <TableRow key={e.id}>
                    <TableCell className="font-semibold text-slate-900">
                      <Link
                        href={`/projects/${projectId}/experiments/${e.id}`}
                        className="text-brand-600 hover:text-brand-700 hover:underline"
                        data-testid={`experiment-link-${e.id}`}
                      >
                        {e.name}
                      </Link>
                      {e.description && (
                        <p className="text-xs text-slate-500 font-normal mt-0.5 max-w-xs truncate">
                          {e.description}
                        </p>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge variant="neutral">{e.experiment_type.replace(/_/g, " ")}</Badge>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={e.status} />
                    </TableCell>
                    <TableCell className="font-mono text-xs text-slate-600">
                      {e.baseline?.model_id ? e.baseline.model_id.slice(0, 8) : "default"}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-slate-600">
                      {e.candidate?.model_id ? e.candidate.model_id.slice(0, 8) : "default"}
                    </TableCell>
                    <TableCell className="text-xs text-slate-500 font-mono">
                      {new Date(e.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-right">
                      <Link href={`/projects/${projectId}/experiments/${e.id}`}>
                        <Button variant="secondary" size="sm">
                          Compare Details →
                        </Button>
                      </Link>
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
