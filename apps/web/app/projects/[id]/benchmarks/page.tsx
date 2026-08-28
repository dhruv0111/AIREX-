"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Alert } from "@/components/ui/Alert";
import { Card } from "@/components/ui/Card";
import yaml from "js-yaml";

const STATUS_STYLES: Record<string, string> = {
  QUEUED: "bg-slate-100 text-slate-600 border-slate-200",
  RUNNING: "bg-blue-50 text-blue-700 border-blue-200 animate-pulse",
  COMPLETED: "bg-emerald-50 text-emerald-700 border-emerald-200",
  FAILED: "bg-rose-50 text-rose-700 border-rose-200",
  CANCELLED: "bg-slate-100 text-slate-500 border-slate-200",
};

export default function BenchmarksPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const router = useRouter();
  const queryClient = useQueryClient();

  const [activeSuiteId, setActiveSuiteId] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [suiteName, setSuiteName] = useState("");
  const [suiteDesc, setSuiteDesc] = useState("");
  const [yamlConfig, setYamlConfig] = useState(
    `# Paste benchmark YAML configuration here\nbenchmark:\n  name: "Reliability Benchmark"\n  description: "Dynamic candidate assessment"\n  dataset: "production-dataset"\n  baseline:\n    model: "gpt-4o"\n  candidates:\n    - model: "claude-3-5"\n  weights:\n    accuracy: 0.4\n    latency_ms: 0.2\n    estimated_cost: 0.1\n    consistency: 0.1\n    safety: 0.2\n  evaluators:\n    - type: "exact_match"\n      enabled: true`
  );
  const [createError, setCreateError] = useState<string | null>(null);

  // Queries
  const suites = useQuery({
    queryKey: ["benchmarks", projectId],
    queryFn: async () => {
      const res = await api.listBenchmarkSuites(projectId);
      const data = res.data;
      if (data && data.length > 0 && !activeSuiteId) {
        setActiveSuiteId(data[0].id);
      }
      return data;
    },
  });

  const runs = useQuery({
    queryKey: ["benchmark-runs", activeSuiteId],
    queryFn: async () => {
      if (!activeSuiteId) return [];
      const res = await api.listBenchmarkRuns(activeSuiteId);
      return res.data;
    },
    enabled: !!activeSuiteId,
    refetchInterval: (query) =>
      query.state.data?.some((r) => r.status === "QUEUED" || r.status === "RUNNING")
        ? 3000
        : false,
  });

  // Mutations
  const createSuiteMutation = useMutation({
    mutationFn: async (payload: { name: string; description?: string; configuration: any }) => {
      const res = await api.createBenchmarkSuite(projectId, payload);
      return res.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["benchmarks", projectId] });
      setActiveSuiteId(data.id);
      setShowCreateModal(false);
      setSuiteName("");
      setSuiteDesc("");
      setCreateError(null);
    },
    onError: (err: any) => {
      setCreateError(err.message || "Failed to create benchmark suite.");
    },
  });

  const triggerRunMutation = useMutation({
    mutationFn: async (suiteId: string) => {
      const res = await api.triggerBenchmarkRun(suiteId, {});
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["benchmark-runs", activeSuiteId] });
    },
  });

  const handleCreateSuite = (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const parsed = yaml.load(yamlConfig) as any;
      if (!parsed || !parsed.benchmark) {
        throw new Error("YAML config must contain a root 'benchmark' key.");
      }
      
      createSuiteMutation.mutate({
        name: suiteName || parsed.benchmark.name || "Benchmark Suite",
        description: suiteDesc || parsed.benchmark.description || null,
        configuration: {
          dataset_version_id: parsed.benchmark.dataset_version_id || null, // UI resolves version, or we can configure it
          dataset: parsed.benchmark.dataset,
          baseline: parsed.benchmark.baseline,
          candidates: parsed.benchmark.candidates,
          weights: parsed.benchmark.weights,
          evaluators: parsed.benchmark.evaluators,
        },
      });
    } catch (err: any) {
      setCreateError(err.message || "Invalid YAML configuration format.");
    }
  };

  const activeSuite = suites.data?.find((s) => s.id === activeSuiteId);

  return (
    <AppShell>
      <div className="flex items-center justify-between">
        <div>
          <Link href={`/projects/${projectId}`} className="text-sm text-brand hover:underline">
            ← Project Details
          </Link>
          <h1 className="mt-2 text-2xl font-bold text-slate-900">Reliability Benchmarking</h1>
          <p className="text-sm text-slate-500 mt-1">
            Conduct multi-variant model benchmarks, monitor statistical evidence, and inspect regressions.
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand/90 transition"
        >
          Create Benchmark Suite
        </button>
      </div>

      <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-4">
        {/* Sidebar Suites list */}
        <div className="lg:col-span-1 flex flex-col gap-4">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400">Benchmark Suites</h2>
          {suites.isLoading ? (
            <p className="text-sm text-slate-400">Loading suites…</p>
          ) : !suites.data?.length ? (
            <div className="rounded-lg border border-dashed border-slate-200 p-4 text-center">
              <p className="text-xs text-slate-500">No benchmark suites configured yet.</p>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {suites.data.map((suite) => (
                <button
                  key={suite.id}
                  onClick={() => setActiveSuiteId(suite.id)}
                  className={`w-full text-left p-3 rounded-lg border text-sm transition ${
                    activeSuiteId === suite.id
                      ? "border-brand bg-brand/5 font-semibold text-slate-900"
                      : "border-slate-200 hover:bg-slate-50 text-slate-600"
                  }`}
                >
                  <p className="truncate">{suite.name}</p>
                  {suite.description && (
                    <p className="text-xs text-slate-400 font-normal truncate mt-0.5">{suite.description}</p>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Runs and Details area */}
        <div className="lg:col-span-3 flex flex-col gap-6">
          {activeSuite ? (
            <>
              {/* Active Suite header */}
              <div className="flex items-start justify-between border-b pb-4">
                <div>
                  <h2 className="text-lg font-bold text-slate-900">{activeSuite.name}</h2>
                  {activeSuite.description && (
                    <p className="text-sm text-slate-500 mt-1">{activeSuite.description}</p>
                  )}
                  <p className="text-xs text-slate-400 mt-2">Suite ID: {activeSuite.id}</p>
                </div>
                <button
                  onClick={() => triggerRunMutation.mutate(activeSuite.id)}
                  disabled={triggerRunMutation.isPending}
                  className="rounded-md border border-brand text-brand bg-white px-3 py-1.5 text-sm font-semibold hover:bg-brand/5 shadow-sm transition disabled:opacity-50"
                >
                  {triggerRunMutation.isPending ? "Triggering…" : "Trigger Run"}
                </button>
              </div>

              {/* Runs Table */}
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-4">Execution History</h3>
                {runs.isLoading ? (
                  <Card>
                    <p className="text-sm text-slate-400">Loading benchmark runs…</p>
                  </Card>
                ) : !runs.data?.length ? (
                  <Card>
                    <div className="text-center py-8">
                      <p className="text-sm text-slate-500">No benchmark runs triggered yet.</p>
                      <button
                        onClick={() => triggerRunMutation.mutate(activeSuite.id)}
                        className="mt-4 text-xs font-semibold text-brand hover:underline"
                      >
                        Trigger the first run →
                      </button>
                    </div>
                  </Card>
                ) : (
                  <Card className="overflow-hidden">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b text-left text-slate-500 bg-slate-50/50">
                          <th className="py-3 px-4">Run ID</th>
                          <th className="py-3 px-4">Status</th>
                          <th className="py-3 px-4">Reliability Score</th>
                          <th className="py-3 px-4">Methodology</th>
                          <th className="py-3 px-4">Executed</th>
                        </tr>
                      </thead>
                      <tbody>
                        {runs.data.map((run) => (
                          <tr
                            key={run.id}
                            className="border-b hover:bg-slate-50/50 cursor-pointer"
                            onClick={() => router.push(`/projects/${projectId}/benchmarks/runs/${run.id}`)}
                          >
                            <td className="py-3 px-4 font-semibold text-brand hover:underline">
                              {run.id.slice(0, 8)}…
                            </td>
                            <td className="py-3 px-4">
                              <span
                                className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold ${
                                  STATUS_STYLES[run.status] || "bg-slate-100 text-slate-600 border-slate-200"
                                }`}
                              >
                                {run.status}
                              </span>
                            </td>
                            <td className="py-3 px-4 font-semibold text-slate-900">
                              {run.reliability_score !== null && run.reliability_score !== undefined
                                ? (run.reliability_score * 100).toFixed(1) + "%"
                                : "—"}
                            </td>
                            <td className="py-3 px-4 text-slate-500">{run.methodology_version}</td>
                            <td className="py-3 px-4 text-slate-400 text-xs">
                              {new Date(run.created_at).toLocaleString()}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </Card>
                )}
              </div>
            </>
          ) : (
            <Card className="flex flex-col items-center justify-center py-12 text-center border-dashed">
              <p className="text-slate-400 text-sm">Select or create a benchmark suite to start.</p>
            </Card>
          )}
        </div>
      </div>

      {/* Creation Modal Dialog */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm transition-all p-4">
          <div className="relative w-full max-w-2xl bg-white rounded-xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[90vh]">
            <div className="p-6 border-b flex items-center justify-between">
              <h3 className="text-lg font-bold text-slate-900">Create Benchmark Suite</h3>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-slate-400 hover:text-slate-600 transition"
              >
                ✕
              </button>
            </div>
            
            <form onSubmit={handleCreateSuite} className="flex flex-col flex-1 overflow-hidden">
              <div className="p-6 overflow-y-auto flex flex-col gap-4 flex-1">
                {createError && <Alert kind="error">{createError}</Alert>}

                <div className="grid grid-cols-2 gap-4">
                  <div className="flex flex-col gap-1.5">
                    <label htmlFor="suiteNameInput" className="text-xs font-bold text-slate-500">Suite Name</label>
                    <input
                      id="suiteNameInput"
                      type="text"
                      required
                      value={suiteName}
                      onChange={(e) => setSuiteName(e.target.value)}
                      placeholder="e.g. Production Model Assessment"
                      className="rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand focus:ring-1 focus:ring-brand outline-none"
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label htmlFor="suiteDescInput" className="text-xs font-bold text-slate-500">Description</label>
                    <input
                      id="suiteDescInput"
                      type="text"
                      value={suiteDesc}
                      onChange={(e) => setSuiteDesc(e.target.value)}
                      placeholder="Optional details"
                      className="rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand focus:ring-1 focus:ring-brand outline-none"
                    />
                  </div>
                </div>

                <div className="flex flex-col gap-1.5 flex-1">
                  <label htmlFor="yamlConfigInput" className="text-xs font-bold text-slate-500">YAML Configuration</label>
                  <p className="text-xs text-slate-400">
                    Define baseline, candidates, scoring weights, and evaluators.
                  </p>
                  <textarea
                    id="yamlConfigInput"
                    required
                    rows={12}
                    value={yamlConfig}
                    onChange={(e) => setYamlConfig(e.target.value)}
                    className="flex-1 font-mono text-xs rounded-lg border border-slate-200 p-3 bg-slate-900 text-slate-100 outline-none focus:border-brand focus:ring-1 focus:ring-brand resize-none min-h-[250px]"
                  />
                </div>
              </div>

              <div className="p-6 border-t bg-slate-50 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="rounded-md border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createSuiteMutation.isPending}
                  className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand/90 transition"
                >
                  {createSuiteMutation.isPending ? "Creating…" : "Save Suite"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AppShell>
  );
}
