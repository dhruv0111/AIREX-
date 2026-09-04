"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Card } from "@/components/ui/Card";
import { Alert } from "@/components/ui/Alert";

export default function AgentRunsPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const router = useRouter();
  const queryClient = useQueryClient();

  const [showRunModal, setShowRunModal] = useState(false);
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [instruction, setInstruction] = useState("Execute calculation 24 * 7 and produce the result.");
  const [simOption, setSimOption] = useState<"standard" | "loop" | "recover" | "forbidden">("standard");
  const [runError, setRunError] = useState<string | null>(null);

  // Queries
  const agentsQuery = useQuery({
    queryKey: ["agents", projectId],
    queryFn: async () => {
      const res = await api.listAgents(projectId);
      return res.data;
    },
  });

  const runsQuery = useQuery({
    queryKey: ["agent-runs", projectId],
    queryFn: async () => {
      const res = await api.listAgentRuns(projectId);
      return res.data;
    },
  });

  const agents = agentsQuery.data ?? [];
  const runs = runsQuery.data ?? [];
  const effectiveAgentId = selectedAgentId || (agents[0]?.id ?? "");

  // Mutation
  const triggerRunMutation = useMutation({
    mutationFn: async () => {
      setRunError(null);
      if (!effectiveAgentId) throw new Error("Please select an agent.");

      const meta: Record<string, any> = {};
      if (simOption === "loop") meta.simulate_loop = true;
      if (simOption === "recover") meta.simulate_failure_and_recover = true;
      if (simOption === "forbidden") meta.simulate_forbidden_tool = true;

      const task = {
        task_id: "task_" + Date.now(),
        instruction,
        forbidden_tools: ["forbidden_tool", "delete_database"],
        max_steps: 15,
        max_tool_calls: 25,
        metadata: meta,
      };

      const res = await api.startAgentRun(projectId, effectiveAgentId, { task });
      return res.data;
    },
    onSuccess: (data) => {
      setShowRunModal(false);
      queryClient.invalidateQueries({ queryKey: ["agent-runs", projectId] });
      router.push(`/projects/${projectId}/agent-runs/${data.id}`);
    },
    onError: (err: any) => {
      setRunError(err?.message || "Failed to start agent run.");
    },
  });

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <div className="flex items-center gap-2 text-sm text-slate-400 mb-1">
              <Link href={`/projects/${projectId}`} className="hover:text-slate-200">
                Project
              </Link>
              <span>/</span>
              <Link href={`/projects/${projectId}/agents`} className="hover:text-slate-200">
                Agents
              </Link>
              <span>/</span>
              <span className="text-slate-200">Execution Runs</span>
            </div>
            <h1 className="text-2xl font-bold text-slate-100">Agent Trajectory Runs</h1>
            <p className="text-sm text-slate-400 mt-1">
              Multi-step execution trajectories, reliability scores, and safety evaluations.
            </p>
          </div>

          <button
            onClick={() => {
              if (agents.length > 0) setSelectedAgentId(agents[0].id);
              setShowRunModal(true);
            }}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg shadow-sm transition"
          >
            + Trigger Agent Run
          </button>
        </div>

        {/* Runs Table */}
        <Card className="overflow-hidden border-slate-800">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-900/80 text-xs uppercase font-semibold text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="px-5 py-3">Run ID</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3">Goal Completion</th>
                  <th className="px-5 py-3 text-center">Reliability Score</th>
                  <th className="px-5 py-3 text-center">Steps</th>
                  <th className="px-5 py-3 text-center">Tool Calls</th>
                  <th className="px-5 py-3 text-center">Safety / Loops</th>
                  <th className="px-5 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {runsQuery.isLoading ? (
                  <tr>
                    <td colSpan={8} className="px-5 py-8 text-center text-slate-500 animate-pulse">
                      Loading agent runs...
                    </td>
                  </tr>
                ) : runs.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-5 py-12 text-center text-slate-400">
                      No agent runs executed yet. Click &quot;+ Trigger Agent Run&quot; to execute a task trajectory.
                    </td>
                  </tr>
                ) : (
                  runs.map((run) => (
                    <tr key={run.id} className="hover:bg-slate-900/40 transition">
                      <td className="px-5 py-4 font-mono text-xs text-blue-400">
                        <Link href={`/projects/${projectId}/agent-runs/${run.id}`} className="hover:underline">
                          {run.id.substring(0, 8)}...
                        </Link>
                      </td>
                      <td className="px-5 py-4">
                        <span
                          className={`px-2 py-0.5 rounded text-xs font-semibold ${
                            run.status === "COMPLETED"
                              ? "bg-emerald-500/15 text-emerald-400"
                              : run.status === "RUNNING"
                              ? "bg-blue-500/15 text-blue-400 animate-pulse"
                              : "bg-rose-500/15 text-rose-400"
                          }`}
                        >
                          {run.status}
                        </span>
                      </td>
                      <td className="px-5 py-4">
                        <span
                          className={`text-xs font-medium ${
                            run.goal_completion_status === "COMPLETED"
                              ? "text-emerald-400"
                              : run.goal_completion_status === "PARTIAL"
                              ? "text-amber-400"
                              : "text-rose-400"
                          }`}
                        >
                          ● {run.goal_completion_status}
                        </span>
                      </td>
                      <td className="px-5 py-4 text-center font-bold">
                        {run.reliability_score !== null ? (
                          <span
                            className={
                              run.reliability_score >= 80
                                ? "text-emerald-400"
                                : run.reliability_score >= 60
                                ? "text-amber-400"
                                : "text-rose-400"
                            }
                          >
                            {run.reliability_score} / 100
                          </span>
                        ) : (
                          <span className="text-slate-500 font-normal">N/A</span>
                        )}
                      </td>
                      <td className="px-5 py-4 text-center text-slate-300 font-mono text-xs">{run.total_steps}</td>
                      <td className="px-5 py-4 text-center text-slate-300 font-mono text-xs">{run.total_tool_calls}</td>
                      <td className="px-5 py-4 text-center text-xs">
                        {run.safety_violations > 0 ? (
                          <span className="px-1.5 py-0.5 bg-red-500/20 text-red-400 rounded font-semibold">
                            ⚠️ {run.safety_violations} Safety
                          </span>
                        ) : run.loops_detected > 0 ? (
                          <span className="px-1.5 py-0.5 bg-amber-500/20 text-amber-400 rounded">
                            🔄 {run.loops_detected} Loop
                          </span>
                        ) : (
                          <span className="text-emerald-400">✓ Clean</span>
                        )}
                      </td>
                      <td className="px-5 py-4 text-right">
                        <Link
                          href={`/projects/${projectId}/agent-runs/${run.id}`}
                          className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded transition"
                        >
                          View Trajectory →
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Trigger Run Modal */}
        {showRunModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
            <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-lg w-full p-6 space-y-4 shadow-xl">
              <h3 className="text-lg font-bold text-slate-100">Trigger Agent Task Trajectory</h3>
              {runError && <Alert kind="error">{runError}</Alert>}

              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1">Target Agent *</label>
                  <select
                    value={effectiveAgentId}
                    onChange={(e) => setSelectedAgentId(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
                  >
                    {agents.map((ag) => (
                      <option key={ag.id} value={ag.id}>
                        {ag.name} (v{ag.version} - {ag.agent_type})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1">Task Instruction *</label>
                  <textarea
                    rows={3}
                    value={instruction}
                    onChange={(e) => setInstruction(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1">Test Simulation Scenario</label>
                  <select
                    data-testid="sim-scenario-select"
                    value={simOption}
                    onChange={(e) => setSimOption(e.target.value as any)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
                  >
                    <option value="standard">Standard Nominal Execution (Success)</option>
                    <option value="recover">Simulate Failure & Recovery (Fault Tolerance)</option>
                    <option value="loop">Simulate Loop Behavior (Loop Detector Test)</option>
                    <option value="forbidden">Simulate Forbidden Tool Call (Safety Blocking Test)</option>
                  </select>
                  <p className="text-xs text-slate-500 mt-1">
                    Deterministic test options to verify multi-step trajectory evaluation and safety bounds.
                  </p>
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowRunModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-medium rounded-lg transition"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={!effectiveAgentId || triggerRunMutation.isPending}
                  onClick={() => triggerRunMutation.mutate()}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition disabled:opacity-50"
                >
                  {triggerRunMutation.isPending ? "Executing..." : "Start Trajectory Run"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
