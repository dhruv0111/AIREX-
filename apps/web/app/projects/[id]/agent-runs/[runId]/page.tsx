"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Card } from "@/components/ui/Card";
import { Alert } from "@/components/ui/Alert";

export default function AgentRunDetailPage() {
  const params = useParams<{ id: string; runId: string }>();
  const projectId = params.id;
  const runId = params.runId;
  const queryClient = useQueryClient();

  const [expandedSteps, setExpandedSteps] = useState<Record<number, boolean>>({});

  const runQuery = useQuery({
    queryKey: ["agent-run", projectId, runId],
    queryFn: async () => {
      const res = await api.getAgentRun(projectId, runId);
      return res.data;
    },
  });

  const trajectoryQuery = useQuery({
    queryKey: ["agent-run-trajectory", projectId, runId],
    queryFn: async () => {
      const res = await api.getAgentRunTrajectory(projectId, runId);
      return res.data;
    },
  });

  const evaluateMutation = useMutation({
    mutationFn: async () => {
      return api.evaluateAgentRun(projectId, runId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agent-run", projectId, runId] });
      queryClient.invalidateQueries({ queryKey: ["agent-run-trajectory", projectId, runId] });
    },
  });

  const toggleStep = (stepNo: number) => {
    setExpandedSteps((prev) => ({ ...prev, [stepNo]: !prev[stepNo] }));
  };

  const run = runQuery.data;
  const steps = trajectoryQuery.data ?? [];
  const breakdown = run?.reliability_breakdown?.dimensions || {};
  const checks = run?.evaluation_checks || [];

  const isBlocked = (run?.safety_violations ?? 0) > 0;

  return (
    <AppShell>
      <div className="space-y-8">
        {/* Breadcrumb & Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <div className="flex items-center gap-2 text-sm text-slate-400 mb-1">
              <Link href={`/projects/${projectId}`} className="hover:text-slate-200">
                Project
              </Link>
              <span>/</span>
              <Link href={`/projects/${projectId}/agent-runs`} className="hover:text-slate-200">
                Agent Runs
              </Link>
              <span>/</span>
              <span className="text-slate-200 font-mono">{runId.substring(0, 8)}</span>
            </div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-slate-100">Trajectory Explorer</h1>
              {run && (
                <span
                  className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                    run.status === "COMPLETED"
                      ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                      : "bg-rose-500/15 text-rose-400 border border-rose-500/30"
                  }`}
                >
                  {run.status}
                </span>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3">
            {run?.trace_id && (
              <span className="text-xs font-mono bg-slate-900 px-3 py-1.5 rounded border border-slate-800 text-slate-400">
                Observability Trace: <span className="text-indigo-400">{run.trace_id}</span>
              </span>
            )}
            <button
              onClick={() => evaluateMutation.mutate()}
              disabled={evaluateMutation.isPending}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg transition border border-slate-700 disabled:opacity-50"
            >
              {evaluateMutation.isPending ? "Evaluating..." : "Re-evaluate Trajectory"}
            </button>
          </div>
        </div>

        {/* Blocking Safety Alert */}
        {isBlocked && (
          <div className="p-4 bg-red-950/40 border border-red-500/50 rounded-xl flex items-start gap-3">
            <span className="text-2xl">🚨</span>
            <div>
              <h3 className="text-sm font-bold text-red-300 uppercase tracking-wide">
                Critical Safety Invariant Triggered — Deployment Strictly Blocked
              </h3>
              <p className="text-xs text-red-200/90 mt-1 leading-relaxed">
                The agent committed {run?.safety_violations} safety violation(s) (such as invoking forbidden tools or
                unauthorized critical actions). Per the AIREX Safety Invariant, this agent trajectory cannot be approved
                regardless of aggregate score.
              </p>
            </div>
          </div>
        )}

        {/* Loop Alert */}
        {(run?.loops_detected ?? 0) > 0 && (
          <div className="p-4 bg-amber-950/40 border border-amber-500/50 rounded-xl flex items-start gap-3">
            <span className="text-2xl">🔄</span>
            <div>
              <h3 className="text-sm font-bold text-amber-300 uppercase tracking-wide">
                Repetitive Execution Loop Detected
              </h3>
              <p className="text-xs text-amber-200/90 mt-1 leading-relaxed">
                Deterministic analysis found repeated cyclic tool invocations without meaningful state progression.
              </p>
            </div>
          </div>
        )}

        {/* Top Metric Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="p-5 border-slate-800 space-y-1">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Agent Reliability Score</span>
            <div className="flex items-baseline gap-2 pt-1">
              <span className={`text-3xl font-extrabold ${isBlocked ? "text-red-400" : (run?.reliability_score ?? 0) >= 80 ? "text-emerald-400" : "text-amber-400"}`}>
                {run?.reliability_score ?? "N/A"}
              </span>
              <span className="text-slate-500 text-xs font-medium">/ 100</span>
            </div>
            <span className={`text-xs font-semibold ${isBlocked ? "text-red-400" : "text-emerald-400"}`}>
              {isBlocked ? "● BLOCKED" : "● READY"}
            </span>
          </Card>

          <Card className="p-5 border-slate-800 space-y-1">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Goal Completion</span>
            <div className="text-xl font-bold text-slate-100 pt-1 flex items-center gap-2">
              <span className={run?.goal_completion_status === "COMPLETED" ? "text-emerald-400" : "text-rose-400"}>
                {run?.goal_completion_status === "COMPLETED" ? "✓" : "✗"}
              </span>
              {run?.goal_completion_status || "UNKNOWN"}
            </div>
            <span className="text-xs text-slate-400">Total Steps: {run?.total_steps || 0}</span>
          </Card>

          <Card className="p-5 border-slate-800 space-y-1">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Tool Invocations</span>
            <div className="text-2xl font-bold text-slate-100 pt-1">
              {run?.successful_tool_calls} <span className="text-slate-500 text-sm font-normal">/ {run?.total_tool_calls} ok</span>
            </div>
            <span className="text-xs text-emerald-400 font-medium">
              Recovered: {run?.recovered_failures || 0} failure(s)
            </span>
          </Card>

          <Card className="p-5 border-slate-800 space-y-1">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Execution Latency</span>
            <div className="text-2xl font-bold text-slate-100 pt-1">
              {run?.duration_ms ? `${(run.duration_ms / 1000).toFixed(2)}s` : "N/A"}
            </div>
            <span className="text-xs text-slate-400 font-mono">
              Agent v{run?.agent_version}
            </span>
          </Card>
        </div>

        {/* 5-Dimension Reliability Breakdown */}
        {Object.keys(breakdown).length > 0 && (
          <Card className="p-6 border-slate-800 space-y-4">
            <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">
              5-Dimension Reliability Breakdown (v1.0.0 Methodology)
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4 pt-1">
              {Object.entries(breakdown).map(([dim, data]: [string, any]) => (
                <div key={dim} className="space-y-1.5 bg-slate-900/60 p-3.5 rounded-lg border border-slate-800/80">
                  <div className="flex justify-between text-xs text-slate-400">
                    <span className="capitalize">{dim.replace("_", " ")}</span>
                    <span className="font-semibold text-slate-300">{Math.round(data.score)}%</span>
                  </div>
                  <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${
                        data.score >= 80 ? "bg-emerald-500" : data.score >= 60 ? "bg-amber-500" : "bg-rose-500"
                      }`}
                      style={{ width: `${Math.max(0, Math.min(100, data.score))}%` }}
                    />
                  </div>
                  <div className="text-[10px] text-slate-500 text-right">Weight: {(data.weight * 100).toFixed(0)}%</div>
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Interactive Trajectory Explorer Timeline */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-200">
              Interactive Execution Trajectory ({steps.length} Steps)
            </h2>
            <div className="flex gap-2">
              <button
                onClick={() => {
                  const all: Record<number, boolean> = {};
                  steps.forEach((s) => (all[s.step_number] = true));
                  setExpandedSteps(all);
                }}
                className="text-xs text-slate-400 hover:text-slate-200"
              >
                Expand All
              </button>
              <span className="text-slate-600">|</span>
              <button
                onClick={() => setExpandedSteps({})}
                className="text-xs text-slate-400 hover:text-slate-200"
              >
                Collapse All
              </button>
            </div>
          </div>

          <div className="relative pl-6 space-y-4 border-l-2 border-slate-800">
            {steps.map((step) => {
              const isExpanded = !!expandedSteps[step.step_number];
              const isToolCall = step.step_type === "TOOL_CALL";
              const isToolResult = step.step_type === "TOOL_RESULT";
              const isFinal = step.step_type === "FINAL";
              const isError = step.status === "FAIL" || !!step.error_message;

              return (
                <div key={step.id} className="relative group">
                  {/* Step node dot on timeline */}
                  <div
                    className={`absolute -left-[31px] top-3 w-4 h-4 rounded-full border-2 bg-slate-950 ${
                      isError
                        ? "border-rose-500 bg-rose-500/20"
                        : isFinal
                        ? "border-emerald-500 bg-emerald-500/20"
                        : isToolCall
                        ? "border-indigo-500 bg-indigo-500/20"
                        : "border-blue-500 bg-blue-500/20"
                    }`}
                  />

                  {/* Step Box */}
                  <Card className={`p-4 border-slate-800 transition ${isError ? "border-rose-500/40" : ""}`}>
                    <div
                      className="flex items-center justify-between cursor-pointer select-none"
                      onClick={() => toggleStep(step.step_number)}
                    >
                      <div className="flex items-center gap-3">
                        <span className="px-2 py-0.5 rounded text-xs font-mono font-semibold bg-slate-800 text-slate-300">
                          #{step.step_number}
                        </span>
                        <span
                          className={`text-xs px-2.5 py-0.5 rounded font-semibold uppercase ${
                            isToolCall
                              ? "bg-indigo-500/15 text-indigo-300 border border-indigo-500/30"
                              : isToolResult
                              ? "bg-purple-500/15 text-purple-300"
                              : isFinal
                              ? "bg-emerald-500/15 text-emerald-300"
                              : "bg-blue-500/15 text-blue-300"
                          }`}
                        >
                          {step.step_type}
                        </span>
                        {step.tool_name && (
                          <span className="text-xs font-mono font-bold text-slate-100">
                            {step.tool_name}()
                          </span>
                        )}
                        {step.duration_ms && (
                          <span className="text-xs text-slate-500">
                            {step.duration_ms.toFixed(0)}ms
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-2">
                        <span
                          className={`text-xs font-semibold ${
                            isError ? "text-rose-400" : "text-emerald-400"
                          }`}
                        >
                          {isError ? "FAIL" : "SUCCESS"}
                        </span>
                        <span className="text-slate-500 text-xs">
                          {isExpanded ? "▲" : "▼"}
                        </span>
                      </div>
                    </div>

                    {/* Step Body Preview / Expanded */}
                    {isExpanded && (
                      <div className="mt-3 pt-3 border-t border-slate-800/80 space-y-2 text-xs">
                        {step.model_input && (
                          <div>
                            <span className="text-slate-400 font-semibold block mb-0.5">Instruction / Input:</span>
                            <div className="p-2.5 bg-slate-950 rounded text-slate-300 font-mono whitespace-pre-wrap">
                              {step.model_input}
                            </div>
                          </div>
                        )}

                        {step.tool_arguments && (
                          <div>
                            <span className="text-slate-400 font-semibold block mb-0.5">Tool Arguments:</span>
                            <pre className="p-2.5 bg-slate-950 rounded text-indigo-200 font-mono overflow-x-auto">
                              {JSON.stringify(step.tool_arguments, null, 2)}
                            </pre>
                          </div>
                        )}

                        {step.tool_result && (
                          <div>
                            <span className="text-slate-400 font-semibold block mb-0.5">Tool Result Output:</span>
                            <pre className="p-2.5 bg-slate-950 rounded text-emerald-200 font-mono overflow-x-auto">
                              {JSON.stringify(step.tool_result, null, 2)}
                            </pre>
                          </div>
                        )}

                        {step.error_message && (
                          <div className="p-2.5 bg-rose-950/40 border border-rose-500/30 rounded text-rose-300 font-mono">
                            <span className="font-bold">Error:</span> {step.error_message}
                          </div>
                        )}

                        {step.model_output && (
                          <div>
                            <span className="text-slate-400 font-semibold block mb-0.5">Synthesized Final Answer:</span>
                            <div className="p-2.5 bg-emerald-950/20 border border-emerald-500/20 rounded text-emerald-200 font-sans whitespace-pre-wrap">
                              {step.model_output}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </Card>
                </div>
              );
            })}
          </div>
        </div>

        {/* Trajectory Checks Table */}
        {checks.length > 0 && (
          <Card className="p-6 border-slate-800 space-y-4">
            <h3 className="text-base font-semibold text-slate-100">Deterministic Trajectory Evaluation Checks</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-900/80 uppercase font-semibold text-slate-400 border-b border-slate-800">
                  <tr>
                    <th className="px-4 py-2.5">Check Name</th>
                    <th className="px-4 py-2.5">Status</th>
                    <th className="px-4 py-2.5">Actual Value</th>
                    <th className="px-4 py-2.5">Expected</th>
                    <th className="px-4 py-2.5">Blocking</th>
                    <th className="px-4 py-2.5">Explanation</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {checks.map((c: any, i: number) => (
                    <tr key={i} className="hover:bg-slate-900/40">
                      <td className="px-4 py-3 font-semibold text-slate-200">{c.check_name}</td>
                      <td className="px-4 py-3">
                        <span
                          className={`px-2 py-0.5 rounded font-bold ${
                            c.status === "PASS"
                              ? "text-emerald-400 bg-emerald-500/10"
                              : c.status === "WARNING"
                              ? "text-amber-400 bg-amber-500/10"
                              : "text-rose-400 bg-rose-500/10"
                          }`}
                        >
                          {c.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-300">{String(c.actual_value)}</td>
                      <td className="px-4 py-3 text-slate-400">{String(c.expected_value)}</td>
                      <td className="px-4 py-3">
                        {c.is_blocking ? (
                          <span className="text-red-400 font-bold">YES</span>
                        ) : (
                          <span className="text-slate-500">NO</span>
                        )}
                      </td>
                      <td className="px-4 py-3 font-sans text-slate-300 max-w-xs truncate">{c.explanation}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
