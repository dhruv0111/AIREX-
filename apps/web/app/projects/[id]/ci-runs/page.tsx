"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Alert } from "@/components/ui/Alert";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

export default function CIRunsPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const [page, setPage] = useState(1);
  const pageSize = 15;

  const ciRunsQuery = useQuery({
    queryKey: ["ci-runs", projectId, page],
    queryFn: () => api.listCIRuns(projectId, { page, page_size: pageSize }),
  });

  const runs = ciRunsQuery.data?.data || [];
  const total = ciRunsQuery.data?.meta?.total || 0;
  const totalPages = Math.ceil(total / pageSize) || 1;

  // Calculate quality trend statistics
  const passedCount = runs.filter((r) => r.outcome === "PASS").length;
  const failedCount = runs.filter((r) => r.outcome === "FAIL").length;
  const totalRuns = runs.length;
  const passRate = totalRuns > 0 ? ((passedCount / totalRuns) * 100).toFixed(0) : "100";

  return (
    <AppShell>
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">CI Run History & Provenance</h1>
          <p className="text-sm text-slate-500">Track pipeline executions, Git metadata provenance, and overall quality gate trends.</p>
        </div>

        {/* Quality Trend Metrics Cards */}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <Card className="p-4 flex flex-col justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase">Total Pipeline Runs</span>
            <span className="text-2xl font-bold text-slate-800 mt-2">{total}</span>
          </Card>
          <Card className="p-4 flex flex-col justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase">Passed Gate Checks</span>
            <span className="text-2xl font-bold text-green-600 mt-2">{passedCount}</span>
          </Card>
          <Card className="p-4 flex flex-col justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase">Failed Gate Checks</span>
            <span className="text-2xl font-bold text-red-600 mt-2">{failedCount}</span>
          </Card>
          <Card className="p-4 flex flex-col justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase">Quality Pass Rate</span>
            <span className="text-2xl font-bold text-indigo-600 mt-2">{passRate}%</span>
          </Card>
        </div>

        {ciRunsQuery.isLoading ? (
          <Card><p className="text-sm text-slate-400">Loading CI runs…</p></Card>
        ) : ciRunsQuery.isError ? (
          <Card><Alert kind="error">{(ciRunsQuery.error as Error).message}</Alert></Card>
        ) : !runs.length ? (
          <Card><p className="text-sm text-slate-500">No CI runs executed yet. Set up a pipeline token in settings to get started.</p></Card>
        ) : (
          <Card>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-slate-500">
                    <th className="py-2 pr-4">Commit</th>
                    <th className="py-2 pr-4">Branch</th>
                    <th className="py-2 pr-4">Repository</th>
                    <th className="py-2 pr-4">CI Provider & ID</th>
                    <th className="py-2 pr-4">Duration</th>
                    <th className="py-2 pr-4">Gate Outcome</th>
                    <th className="py-2 pr-4">Date</th>
                    <th className="py-2">Details</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => (
                    <tr key={run.id} className="border-b hover:bg-slate-50">
                      <td className="py-3 pr-4 font-mono text-slate-900">
                        {run.pull_request_number ? (
                          <a
                            href={run.pull_request_url || "#"}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-brand hover:underline"
                          >
                            PR #{run.pull_request_number}
                          </a>
                        ) : (
                          run.commit_sha.substring(0, 7)
                        )}
                      </td>
                      <td className="py-3 pr-4 text-slate-800">{run.branch}</td>
                      <td className="py-3 pr-4 text-slate-600 truncate max-w-xs">{run.repository}</td>
                      <td className="py-3 pr-4 text-slate-600">
                        <span className="text-xs rounded bg-slate-100 px-1.5 py-0.5 font-mono mr-1">
                          {run.ci_provider}
                        </span>
                        <span className="font-mono text-xs">{run.ci_run_id}</span>
                      </td>
                      <td className="py-3 pr-4 text-slate-600">
                        {run.duration_seconds ? `${run.duration_seconds.toFixed(0)}s` : "—"}
                      </td>
                      <td className="py-3 pr-4">
                        <span
                          className={`rounded px-2 py-0.5 text-xs font-semibold ${
                            run.outcome === "PASS"
                              ? "bg-green-100 text-green-800"
                              : run.outcome === "FAIL"
                              ? "bg-red-100 text-red-800"
                              : "bg-amber-100 text-amber-800"
                          }`}
                        >
                          {run.outcome || run.status}
                        </span>
                      </td>
                      <td className="py-3 pr-4 text-slate-500">
                        {new Date(run.created_at).toLocaleString()}
                      </td>
                      <td className="py-3">
                        {run.experiment_id ? (
                          <Link
                            href={`/projects/${projectId}/experiments/${run.experiment_id}`}
                            className="text-brand hover:underline"
                          >
                            View Experiment
                          </Link>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            {totalPages > 1 ? (
              <div className="flex items-center justify-between mt-4 border-t pt-4">
                <Button
                  variant="secondary"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                >
                  Previous
                </Button>
                <span className="text-xs text-slate-500">
                  Page {page} of {totalPages}
                </span>
                <Button
                  variant="secondary"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                >
                  Next
                </Button>
              </div>
            ) : null}
          </Card>
        )}
      </div>
    </AppShell>
  );
}
