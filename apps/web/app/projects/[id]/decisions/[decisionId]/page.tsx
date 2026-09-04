"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Card, MetricCard } from "@/components/ui/Card";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { Tabs } from "@/components/ui/Tabs";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/Table";

const OUTCOME_CONFIG: Record<string, { variant: "success" | "warning" | "danger" | "neutral"; desc: string }> = {
  APPROVED: { variant: "success", desc: "Model meets all safety, reliability, regression, and quality criteria. Fully verified for deployment." },
  CONDITIONALLY_APPROVED: { variant: "warning", desc: "Approved with non-blocking warnings or stale evidence. Review non-blocking items before broad rollout." },
  REJECTED: { variant: "danger", desc: "Model performance or reliability fell below policy thresholds." },
  BLOCKED: { variant: "danger", desc: "Active critical alert, high regression severity, or failed quality gate blocks deployment." },
  INSUFFICIENT_EVIDENCE: { variant: "neutral", desc: "Required benchmark or evaluation runs are missing. Cannot evaluate release readiness." },
};

const CHECK_VARIANTS: Record<string, "success" | "danger" | "warning" | "neutral"> = {
  PASS: "success",
  FAIL: "danger",
  WARNING: "warning",
  MISSING: "danger",
  STALE: "warning",
  NOT_APPLICABLE: "neutral",
};

export default function DecisionDetailPage() {
  const params = useParams<{ id: string; decisionId: string }>();
  const projectId = params.id;
  const decisionId = params.decisionId;
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<"checks" | "evidence" | "comparison">("checks");

  const decision = useQuery({
    queryKey: ["release-decision", decisionId],
    queryFn: async () => {
      const res = await api.getReleaseDecision(projectId, decisionId);
      return res.data;
    },
    refetchInterval: (query) =>
      query.state.data?.status === "COLLECTING_EVIDENCE" ? 2000 : false,
  });

  const comparison = useQuery({
    queryKey: ["decision-comparison", decisionId],
    queryFn: async () => {
      const res = await api.compareReleaseDecision(projectId, decisionId);
      return res.data;
    },
    enabled: !!decision.data && decision.data.status === "DECIDED",
  });

  const evaluateMutation = useMutation({
    mutationFn: async () => {
      const res = await api.evaluateReleaseDecision(projectId, decisionId);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["release-decision", decisionId] });
      queryClient.invalidateQueries({ queryKey: ["decision-comparison", decisionId] });
    },
  });

  const d = decision.data;
  const outcomeInfo = d?.outcome ? OUTCOME_CONFIG[d.outcome] : null;
  const dimensions = d?.readiness_breakdown?.dimensions || {};
  const recommendations = d?.readiness_breakdown?.recommendations || [];

  return (
    <AppShell>
      <div className="space-y-6" data-testid="decision-detail-view">
        {/* Breadcrumb & Header */}
        <div className="border-b border-slate-200 pb-5">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 mb-1">
            <Link href={`/projects/${projectId}/decisions`} className="hover:text-slate-900 transition">
              ← Back to Decisions
            </Link>
          </div>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight text-slate-900" data-testid="decision-cockpit-title">
                Release Decision Cockpit
              </h1>
              <span className="font-mono text-xs text-slate-600 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                {decisionId.slice(0, 12)}
              </span>
              <StatusBadge status={d?.status} />
            </div>

            <Button
              onClick={() => evaluateMutation.mutate()}
              disabled={evaluateMutation.isPending}
              isLoading={evaluateMutation.isPending}
              data-testid="evaluate-decision-btn"
            >
              Re-Evaluate Quality Gate
            </Button>
          </div>
        </div>

        {/* Outcome Banner & Detailed Human Explanation */}
        {d?.outcome && outcomeInfo && (
          <div
            className={`rounded-2xl border p-6 shadow-sm ${
              outcomeInfo.variant === "success"
                ? "bg-emerald-50/70 border-emerald-200"
                : outcomeInfo.variant === "warning"
                ? "bg-amber-50/70 border-amber-200"
                : "bg-rose-50/70 border-rose-200"
            }`}
            data-testid="decision-outcome-banner"
          >
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <Badge variant={outcomeInfo.variant} size="md" dot>
                    DECISION: {d.outcome}
                  </Badge>
                  <span className="text-xs font-mono text-slate-500">Status: {d.status}</span>
                </div>
                <h2 className="text-2xl font-bold tracking-tight text-slate-900">
                  {d.outcome === "APPROVED"
                    ? "Verified for Production Release"
                    : d.outcome === "CONDITIONALLY_APPROVED"
                    ? "Conditionally Approved — Review Warnings Before Deployment"
                    : `Release Outcome: ${d.outcome}`}
                </h2>
                <p className="text-sm text-slate-700 max-w-2xl leading-relaxed">{outcomeInfo.desc}</p>

                {/* Explanation Summary Bullet Points */}
                <div className="rounded-xl bg-white/80 border border-slate-200/80 p-3.5 text-xs text-slate-700 space-y-1.5 max-w-2xl">
                  <div className="font-semibold text-slate-900 flex items-center gap-1.5">
                    <span>💡 Decision Engine Explanation:</span>
                  </div>
                  {d.outcome === "CONDITIONALLY_APPROVED" ? (
                    <div className="space-y-1 pl-1">
                      <p>• <strong>Core Quality & Safety:</strong> Evaluation test cases and safety rubrics passed policy requirements.</p>
                      <p>• <strong>Condition Reason:</strong> Non-blocking telemetry warnings were detected (e.g. pending production error rates or latency metrics in pre-release staging).</p>
                      <p>• <strong>Recommended Action:</strong> Proceed with canary or staging deployment; monitor telemetry to satisfy production health policies.</p>
                    </div>
                  ) : d.outcome === "APPROVED" ? (
                    <div className="space-y-1 pl-1">
                      <p>• <strong>All Checks Passed:</strong> Quality, safety, reliability, and telemetry checks satisfied all policy thresholds.</p>
                      <p>• <strong>Release Status:</strong> Safe to proceed with full production rollout.</p>
                    </div>
                  ) : (
                    <div className="space-y-1 pl-1">
                      <p>• <strong>Gate Verdict:</strong> {outcomeInfo.desc}</p>
                      <p>• <strong>Action Required:</strong> Review failing checks in the policy evaluation table below.</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Readiness Score Dial Block */}
              <div className="flex items-center gap-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm min-w-[200px] justify-center text-center">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Readiness Score</div>
                  <div className="text-3xl sm:text-4xl font-black text-slate-900 font-mono mt-1" data-testid="readiness-score">
                    {d.readiness_score !== null ? `${d.readiness_score} / 100` : "N/A"}
                  </div>
                  <span className={`text-[11px] font-semibold mt-0.5 block ${
                    d.readiness_score !== null && d.readiness_score >= 80
                      ? "text-emerald-700"
                      : d.readiness_score !== null && d.readiness_score >= 60
                      ? "text-amber-700"
                      : "text-rose-700"
                  }`}>
                    {d.readiness_score !== null && d.readiness_score >= 80
                      ? "Passes Policy Threshold"
                      : d.readiness_score !== null && d.readiness_score >= 60
                      ? "Conditional Approval"
                      : "Below Target"}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Readiness Dimensions */}
        {Object.keys(dimensions).length > 0 && (
          <Card title="Readiness Dimension Breakdown" subtitle="Weighted multi-factor quality and reliability assessment" className="shadow-sm">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {Object.entries(dimensions).map(([key, val]: [string, any]) => {
                const score = val.score;
                const weight = val.weight * 100;
                const barColor = score >= 80 ? "bg-emerald-500" : score >= 60 ? "bg-amber-500" : "bg-rose-500";

                return (
                  <div key={key} className="rounded-xl border border-slate-200 bg-slate-50/50 p-4 space-y-2">
                    <div className="flex justify-between text-xs font-semibold">
                      <span className="text-slate-700 capitalize">{key.replace(/_/g, " ")}</span>
                      <span className="font-mono text-slate-900">{score.toFixed(1)} / 100</span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-slate-200 overflow-hidden">
                      <div className={`h-full ${barColor}`} style={{ width: `${Math.min(100, Math.max(0, score))}%` }} />
                    </div>
                    <div className="text-[10px] text-slate-500 text-right font-medium">Weight: {weight}%</div>
                  </div>
                );
              })}
            </div>
          </Card>
        )}

        {/* Evidence-backed Recommendations */}
        {recommendations.length > 0 && (
          <Card title="Evidence-Backed Action Items" subtitle="Explainable decisions derived from empirical evaluation evidence" className="shadow-sm">
            <div className="space-y-3">
              {recommendations.map((rec: any, idx: number) => (
                <div key={idx} className="rounded-xl border border-slate-200 bg-white p-4 space-y-2 shadow-sm">
                  <div className="flex items-center gap-2">
                    <Badge variant="brand">{rec.type}</Badge>
                    <span className="text-xs font-semibold text-slate-500">Observed Empirical Fact:</span>
                    <span className="text-xs text-slate-800 font-medium">{rec.fact}</span>
                  </div>
                  <div className="pl-3 border-l-2 border-brand-500 text-xs text-slate-700 leading-relaxed">
                    <strong className="text-brand-700">Recommended Action: </strong>
                    {rec.suggestion}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Tabs: Checks | Canonical Evidence | Comparison */}
        <Tabs
          tabs={[
            { id: "checks", label: `Policy Checks (${d?.checks?.length || 0})` },
            { id: "evidence", label: `Canonical Evidence (${d?.evidences?.length || 0})` },
            { id: "comparison", label: "What Changed Since Last Run" },
          ]}
          activeTab={activeTab}
          onChange={setActiveTab}
        />

        {/* Tab 1: Checks Table */}
        {activeTab === "checks" && (
          <Card title="Deterministic Policy Evaluation Table" className="shadow-sm">
            {d?.checks && d.checks.length > 0 ? (
              <Table>
                <TableHeader>
                  <tr>
                    <TableHead>Status</TableHead>
                    <TableHead>Rule Name</TableHead>
                    <TableHead>Actual Value</TableHead>
                    <TableHead>Expected Threshold</TableHead>
                    <TableHead>Blocking</TableHead>
                    <TableHead>Explanation</TableHead>
                  </tr>
                </TableHeader>
                <TableBody>
                  {d.checks.map((chk) => {
                    const variant = CHECK_VARIANTS[chk.status] || "neutral";
                    return (
                      <TableRow key={chk.id}>
                        <TableCell>
                          <Badge variant={variant} dot>
                            {chk.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="font-mono text-xs font-bold text-slate-800">
                          {chk.rule_name}
                        </TableCell>
                        <TableCell className="font-mono text-xs text-slate-900 font-semibold">
                          {chk.actual_value !== null ? String(chk.actual_value) : "None"}
                        </TableCell>
                        <TableCell className="font-mono text-xs text-slate-500">
                          {chk.expected_value !== null ? String(chk.expected_value) : "—"}
                        </TableCell>
                        <TableCell>
                          {chk.is_blocking ? (
                            <Badge variant="danger">YES</Badge>
                          ) : (
                            <span className="text-xs text-slate-400">No</span>
                          )}
                        </TableCell>
                        <TableCell className="text-xs text-slate-600">
                          {chk.explanation}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            ) : (
              <p className="py-8 text-center text-sm text-slate-400">
                No policy checks executed yet. Click "Re-Evaluate Quality Gate" above to run.
              </p>
            )}
          </Card>
        )}

        {/* Tab 2: Canonical Evidence */}
        {activeTab === "evidence" && (
          <Card title="Aggregated Evidence Records" className="shadow-sm">
            {d?.evidences && d.evidences.length > 0 ? (
              <div className="space-y-4">
                {d.evidences.map((ev) => (
                  <div key={ev.id} className="rounded-xl border border-slate-200 bg-slate-50/50 p-4 space-y-3">
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-200/60 pb-3">
                      <div className="flex items-center gap-2.5">
                        <Badge variant="brand">{ev.source_type}</Badge>
                        <span className="font-mono text-xs text-slate-600">ID: {ev.source_id.slice(0, 18)}…</span>
                        {ev.is_fresh ? (
                          <span className="text-[11px] text-emerald-700 font-semibold">● Fresh</span>
                        ) : (
                          <span className="text-[11px] text-amber-700 font-semibold">● Stale</span>
                        )}
                      </div>

                      {ev.source_type === "EVALUATION" && (
                        <Link href={`/projects/${projectId}/evaluations`} className="text-xs font-semibold text-brand-600 hover:underline">
                          View Evaluation Run →
                        </Link>
                      )}
                      {ev.source_type === "OBSERVABILITY" && (
                        <Link href={`/projects/${projectId}/observability`} className="text-xs font-semibold text-brand-600 hover:underline">
                          View Traces →
                        </Link>
                      )}
                    </div>

                    <pre className="rounded-lg bg-white border border-slate-200 p-3 font-mono text-xs text-slate-800 overflow-x-auto">
                      {JSON.stringify(ev.summary, null, 2)}
                    </pre>
                  </div>
                ))}
              </div>
            ) : (
              <p className="py-8 text-center text-sm text-slate-400">No evidence collected yet.</p>
            )}
          </Card>
        )}

        {/* Tab 3: What Changed Comparison */}
        {activeTab === "comparison" && (
          <Card title="Comparison with Previous Release Decision" className="shadow-sm">
            {comparison.data?.metrics && comparison.data.metrics.length > 0 ? (
              <div className="space-y-4">
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-sm font-semibold text-slate-900">{comparison.data.summary}</p>
                  <p className="text-xs text-slate-500 mt-1">
                    Compatibility: {comparison.data.is_compatible ? "Compatible (Same model & environment)" : "Incompatible Baseline"}
                  </p>
                </div>

                <Table>
                  <TableHeader>
                    <tr>
                      <TableHead>Metric</TableHead>
                      <TableHead>Dimension</TableHead>
                      <TableHead>Previous Value</TableHead>
                      <TableHead>Current Value</TableHead>
                      <TableHead>Change Status</TableHead>
                      <TableHead>Explanation</TableHead>
                    </tr>
                  </TableHeader>
                  <TableBody>
                    {comparison.data.metrics.map((m, idx) => (
                      <TableRow key={idx}>
                        <TableCell className="font-semibold text-slate-900">{m.metric_name}</TableCell>
                        <TableCell className="text-xs text-slate-500">{m.dimension}</TableCell>
                        <TableCell className="font-mono text-xs text-slate-600">{String(m.previous_value)}</TableCell>
                        <TableCell className="font-mono text-xs text-slate-900 font-semibold">{String(m.current_value)}</TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              m.change_status === "IMPROVED"
                                ? "success"
                                : m.change_status === "REGRESSED"
                                ? "danger"
                                : "neutral"
                            }
                          >
                            {m.change_status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-xs text-slate-600">{m.explanation}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <p className="py-8 text-center text-sm text-slate-400">
                {comparison.data?.summary || "No prior decision found for baseline comparison."}
              </p>
            )}
          </Card>
        )}

        {/* Metadata Details */}
        <Card title="Decision Lineage & Governance" className="shadow-sm">
          <dl className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 text-xs">
            <div>
              <dt className="text-slate-500">Configuration Fingerprint (SHA-256)</dt>
              <dd className="font-mono text-slate-800 break-all mt-0.5">{d?.configuration_fingerprint}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Policy Version</dt>
              <dd className="font-semibold text-slate-800 mt-0.5">v{d?.policy_version}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Evaluated Timestamp</dt>
              <dd className="text-slate-800 font-mono mt-0.5">{d?.evaluated_at ? new Date(d.evaluated_at).toLocaleString() : "Never"}</dd>
            </div>
          </dl>
        </Card>
      </div>
    </AppShell>
  );
}
