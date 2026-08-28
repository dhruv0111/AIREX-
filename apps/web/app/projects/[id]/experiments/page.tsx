"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Alert } from "@/components/ui/Alert";
import { Card } from "@/components/ui/Card";

const STATUS_STYLES: Record<string, string> = {
  DRAFT: "bg-slate-100 text-slate-600",
  QUEUED: "bg-slate-100 text-slate-600",
  RUNNING: "bg-blue-100 text-blue-700",
  COMPLETED: "bg-green-100 text-green-700",
  FAILED: "bg-red-100 text-red-700",
  CANCELLED: "bg-slate-100 text-slate-500",
  PASS: "bg-green-100 text-green-700",
  FAIL: "bg-red-100 text-red-700",
  INCONCLUSIVE: "bg-amber-100 text-amber-700",
};

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

  return (
    <AppShell>
      <div className="flex items-center justify-between">
        <div>
          <Link href={`/projects/${projectId}`} className="text-sm text-brand hover:underline">
            ← Project
          </Link>
          <h1 className="mt-2 text-2xl font-bold text-slate-900">Experiments & Benchmarks</h1>
        </div>
        <Link
          href={`/projects/${projectId}/experiments/new`}
          className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand/90"
        >
          New Experiment
        </Link>
      </div>

      <div className="mt-6">
        {experiments.isLoading ? (
          <Card>
            <p className="text-sm text-slate-400">Loading experiments…</p>
          </Card>
        ) : experiments.isError ? (
          <Card>
            <Alert kind="error">{(experiments.error as Error).message}</Alert>
          </Card>
        ) : !experiments.data?.data.length ? (
          <Card>
            <div className="text-center py-6">
              <p className="text-sm text-slate-500">No experiments created yet.</p>
              <Link
                href={`/projects/${projectId}/experiments/new`}
                className="mt-4 inline-block text-sm text-brand hover:underline"
              >
                Create your first experiment →
              </Link>
            </div>
          </Card>
        ) : (
          <Card>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-slate-500">
                  <th className="py-3 pr-4">Name</th>
                  <th className="py-3 pr-4">Type</th>
                  <th className="py-3 pr-4">Status / Quality Gate</th>
                  <th className="py-3 pr-4">Baseline Model</th>
                  <th className="py-3 pr-4">Candidate Model</th>
                  <th className="py-3 pr-4">Created</th>
                </tr>
              </thead>
              <tbody>
                {experiments.data.data.map((e) => (
                  <tr key={e.id} className="border-b hover:bg-slate-50/50">
                    <td className="py-3 pr-4 font-semibold text-slate-900">
                      <Link
                        href={`/projects/${projectId}/experiments/${e.id}`}
                        className="hover:underline text-brand"
                      >
                        {e.name}
                      </Link>
                      {e.description && (
                        <p className="text-xs text-slate-400 font-normal mt-0.5 max-w-xs truncate">
                          {e.description}
                        </p>
                      )}
                    </td>
                    <td className="py-3 pr-4 text-slate-600 font-medium">
                      {e.experiment_type.replace("_", " ")}
                    </td>
                    <td className="py-3 pr-4">
                      <span
                        className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                          STATUS_STYLES[e.status] ?? "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {e.status}
                      </span>
                    </td>
                    <td className="py-3 pr-4 text-slate-600 font-mono text-xs">
                      {e.baseline?.model_id ? e.baseline.model_id.slice(0, 8) : "default"}
                    </td>
                    <td className="py-3 pr-4 text-slate-600 font-mono text-xs">
                      {e.candidate?.model_id ? e.candidate.model_id.slice(0, 8) : "default"}
                    </td>
                    <td className="py-3 pr-4 text-slate-500">
                      {new Date(e.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
