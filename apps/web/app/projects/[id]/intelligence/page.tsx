"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Card } from "@/components/ui/Card";
import { Alert } from "@/components/ui/Alert";

const STATUS_BADGES: Record<string, { bg: string; text: string; border: string; icon: string }> = {
  READY: { bg: "bg-emerald-500/10", text: "text-emerald-400", border: "border-emerald-500/30", icon: "✓" },
  AT_RISK: { bg: "bg-amber-500/10", text: "text-amber-400", border: "border-amber-500/30", icon: "⚠" },
  BLOCKED: { bg: "bg-rose-500/10", text: "text-rose-400", border: "border-rose-500/30", icon: "✕" },
  INSUFFICIENT_EVIDENCE: { bg: "bg-slate-500/10", text: "text-slate-400", border: "border-slate-500/30", icon: "○" },
};

const OUTCOME_BADGES: Record<string, { bg: string; text: string; border: string }> = {
  APPROVED: { bg: "bg-emerald-500/15", text: "text-emerald-400", border: "border-emerald-500/40" },
  CONDITIONALLY_APPROVED: { bg: "bg-amber-500/15", text: "text-amber-400", border: "border-amber-500/40" },
  REJECTED: { bg: "bg-rose-500/15", text: "text-rose-400", border: "border-rose-500/40" },
  BLOCKED: { bg: "bg-red-500/20", text: "text-red-400", border: "border-red-500/50" },
  INSUFFICIENT_EVIDENCE: { bg: "bg-slate-500/15", text: "text-slate-400", border: "border-slate-500/40" },
};

export default function ProjectIntelligencePage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;

  const project = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api.getProject(projectId),
  });

  const overview = useQuery({
    queryKey: ["intelligence-overview", projectId],
    queryFn: async () => {
      const res = await api.getIntelligenceOverview(projectId);
      return res.data;
    },
  });

  const actions = useQuery({
    queryKey: ["intelligence-actions", projectId],
    queryFn: async () => {
      const res = await api.getIntelligenceActions(projectId);
      return res.data;
    },
  });

  const statusStyle = STATUS_BADGES[overview.data?.overall_status || "INSUFFICIENT_EVIDENCE"] || STATUS_BADGES.INSUFFICIENT_EVIDENCE;
  const readiness = overview.data?.readiness_score;

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Navigation Breadcrumb */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href={`/projects/${projectId}`} className="text-sm font-medium text-brand hover:underline">
              ← {project.data?.data.name || "Project"}
            </Link>
            <span className="text-slate-400">/</span>
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
              Intelligence & Health Dashboard
            </h1>
          </div>
          <div className="flex gap-2">
            <Link
              href={`/projects/${projectId}/decisions`}
              className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand/90 transition-all"
            >
              Release Decisions →
            </Link>
          </div>
        </div>

        {/* Executive Overall Status Banner */}
        <div
          className={`rounded-xl border p-6 backdrop-blur-md transition-all ${statusStyle.bg} ${statusStyle.border}`}
          data-testid="executive-status-banner"
        >
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-4">
              <div className={`flex h-14 w-14 items-center justify-center rounded-xl border text-2xl font-bold shadow-inner ${statusStyle.bg} ${statusStyle.border} ${statusStyle.text}`}>
                {statusStyle.icon}
              </div>
              <div>
                <div className="text-xs uppercase tracking-wider text-slate-400 font-semibold">Overall Project Health</div>
                <div className={`text-2xl font-extrabold tracking-tight ${statusStyle.text}`}>
                  {overview.data?.overall_status || "INSUFFICIENT_EVIDENCE"}
                </div>
                <p className="text-sm text-slate-400 mt-1">
                  {overview.data?.overall_status === "READY" && "All safety thresholds, reliability scores, and alert rules are verified safe for production."}
                  {overview.data?.overall_status === "AT_RISK" && "Minor warnings or stale evidence detected. Review warnings before broad rollout."}
                  {overview.data?.overall_status === "BLOCKED" && "Critical issues or active alerts block safe deployment to target environment."}
                  {overview.data?.overall_status === "INSUFFICIENT_EVIDENCE" && "Insufficient empirical data. Run benchmark or evaluation suites to establish baseline."}
                </p>
              </div>
            </div>

            {/* Score Pill */}
            <div className="flex items-center gap-3 rounded-lg border border-slate-700/50 bg-slate-900/60 px-5 py-3 shadow-inner">
              <div className="text-right">
                <div className="text-xs text-slate-400 font-medium">Readiness Score</div>
                <div className="text-2xl font-black text-slate-100">
                  {readiness !== null && readiness !== undefined ? `${readiness}/100` : "N/A"}
                </div>
              </div>
              <div className="relative h-12 w-12 flex items-center justify-center">
                <svg className="h-12 w-12 -rotate-90 transform" viewBox="0 0 36 36">
                  <path
                    className="text-slate-700"
                    strokeWidth="3.5"
                    stroke="currentColor"
                    fill="none"
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  />
                  <path
                    className={readiness && readiness >= 80 ? "text-emerald-500" : readiness && readiness >= 60 ? "text-amber-500" : "text-rose-500"}
                    strokeDasharray={`${readiness || 0}, 100`}
                    strokeWidth="3.5"
                    strokeLinecap="round"
                    stroke="currentColor"
                    fill="none"
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  />
                </svg>
              </div>
            </div>
          </div>
        </div>

        {/* Blocking Issues & Warnings Grid */}
        <div className="grid gap-6 md:grid-cols-2">
          {/* Blocking Issues */}
          <Card title="Blocking Issues">
            {overview.data?.blocking_issues && overview.data.blocking_issues.length > 0 ? (
              <ul className="space-y-2">
                {overview.data.blocking_issues.map((b, idx) => (
                  <li key={idx} className="flex items-start gap-2 rounded-lg border border-rose-500/20 bg-rose-500/10 p-3 text-sm text-rose-300">
                    <span className="font-bold text-rose-400">✕</span>
                    <span>{b}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="py-6 text-center text-sm text-slate-400">
                ✓ No blocking deployment issues detected.
              </div>
            )}
          </Card>

          {/* Warnings */}
          <Card title="Warnings & Stale Data">
            {overview.data?.warnings && overview.data.warnings.length > 0 ? (
              <ul className="space-y-2">
                {overview.data.warnings.map((w, idx) => (
                  <li key={idx} className="flex items-start gap-2 rounded-lg border border-amber-500/20 bg-amber-500/10 p-3 text-sm text-amber-300">
                    <span className="font-bold text-amber-400">⚠</span>
                    <span>{w}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="py-6 text-center text-sm text-slate-400">
                ✓ No non-blocking warnings active.
              </div>
            )}
          </Card>
        </div>

        {/* Required Actions Checklist */}
        <Card title="Required Actions">
          {actions.data?.actions && actions.data.actions.length > 0 ? (
            <div className="divide-y divide-slate-800">
              {actions.data.actions.map((act, idx) => (
                <div key={idx} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`rounded px-2 py-0.5 text-xs font-semibold uppercase ${
                          act.priority === "BLOCKING" || act.priority === "CRITICAL"
                            ? "bg-rose-500/20 text-rose-300"
                            : act.priority === "HIGH"
                            ? "bg-amber-500/20 text-amber-300"
                            : "bg-blue-500/20 text-blue-300"
                        }`}
                      >
                        {act.priority}
                      </span>
                      <h4 className="text-sm font-semibold text-slate-200">{act.title}</h4>
                    </div>
                    <p className="text-xs text-slate-400 mt-1">{act.description}</p>
                  </div>
                  {act.action_type === "RUN_BENCHMARK" && (
                    <Link
                      href={`/projects/${projectId}/benchmarks`}
                      className="inline-flex items-center rounded-md border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700"
                    >
                      Go to Benchmarks →
                    </Link>
                  )}
                  {act.action_type === "RUN_EVALUATION" && (
                    <Link
                      href={`/projects/${projectId}/evaluations`}
                      className="inline-flex items-center rounded-md border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700"
                    >
                      Go to Evaluations →
                    </Link>
                  )}
                  {act.action_type === "RESOLVE_ALERT" && (
                    <Link
                      href={`/projects/${projectId}/alerts`}
                      className="inline-flex items-center rounded-md border border-rose-700/50 bg-rose-900/30 px-3 py-1.5 text-xs font-medium text-rose-200 hover:bg-rose-900/50"
                    >
                      Go to Alerts →
                    </Link>
                  )}
                  {act.action_type === "CREATE_DECISION" && (
                    <Link
                      href={`/projects/${projectId}/decisions`}
                      className="inline-flex items-center rounded-md border border-brand/50 bg-brand/20 px-3 py-1.5 text-xs font-medium text-brand hover:bg-brand/30"
                    >
                      Configure Decision →
                    </Link>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-400 py-4 text-center">No action required at this time.</p>
          )}
        </Card>

        {/* Model Comparison Table */}
        <Card title="Compatible Model Comparison">
          {overview.data?.model_comparisons && overview.data.model_comparisons.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-300">
                <thead className="border-b border-slate-800 text-xs uppercase tracking-wider text-slate-400">
                  <tr>
                    <th className="py-3 px-4">Model</th>
                    <th className="py-3 px-4">Readiness Score</th>
                    <th className="py-3 px-4">Latest Outcome</th>
                    <th className="py-3 px-4">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {overview.data.model_comparisons.map((m) => {
                    const outcomeBadge = OUTCOME_BADGES[m.latest_outcome] || OUTCOME_BADGES.INSUFFICIENT_EVIDENCE;
                    return (
                      <tr key={m.model_id} className="hover:bg-slate-800/40">
                        <td className="py-3 px-4 font-semibold text-slate-100">{m.name}</td>
                        <td className="py-3 px-4">
                          {m.readiness_score !== null ? (
                            <span className="font-bold text-slate-200">{m.readiness_score}/100</span>
                          ) : (
                            <span className="text-slate-500">N/A</span>
                          )}
                        </td>
                        <td className="py-3 px-4">
                          <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-semibold ${outcomeBadge.bg} ${outcomeBadge.text} ${outcomeBadge.border}`}>
                            {m.latest_outcome}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <Link
                            href={`/projects/${projectId}/decisions`}
                            className="text-xs text-brand hover:underline font-medium"
                          >
                            View Decisions →
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-slate-400 py-6 text-center">
              No models configured in this project. Add models to enable comparative intelligence.
            </p>
          )}
        </Card>
      </div>
    </AppShell>
  );
}
