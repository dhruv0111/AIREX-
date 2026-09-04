"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Card, MetricCard } from "@/components/ui/Card";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { FormField, Input, Select } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { EmptyState } from "@/components/ui/EmptyState";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/Table";

const OUTCOME_VARIANTS: Record<string, "success" | "warning" | "danger" | "neutral"> = {
  APPROVED: "success",
  CONDITIONALLY_APPROVED: "warning",
  REJECTED: "danger",
  BLOCKED: "danger",
  INSUFFICIENT_EVIDENCE: "neutral",
};

export default function ReleaseDecisionsPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const router = useRouter();
  const queryClient = useQueryClient();

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showPolicyModal, setShowPolicyModal] = useState(false);

  // Form states - Decision
  const [selectedEnv, setSelectedEnv] = useState("");
  const [selectedModel, setSelectedModel] = useState("");
  const [selectedPolicy, setSelectedPolicy] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);

  // Form states - Policy
  const [policyName, setPolicyName] = useState("Production Standard Policy");
  const [minReliability, setMinReliability] = useState("85");
  const [maxRegSeverity, setMaxRegSeverity] = useState("HIGH");
  const [maxErrorRate, setMaxErrorRate] = useState("0.01");
  const [maxCritAlerts, setMaxCritAlerts] = useState("0");
  const [reqBenchmark, setReqBenchmark] = useState(true);
  const [reqEvaluation, setReqEvaluation] = useState(true);
  const [policyError, setPolicyError] = useState<string | null>(null);

  // Queries
  const decisions = useQuery({
    queryKey: ["release-decisions", projectId],
    queryFn: async () => {
      const res = await api.listReleaseDecisions(projectId);
      return res.data;
    },
  });

  const policies = useQuery({
    queryKey: ["release-policies", projectId],
    queryFn: async () => {
      const res = await api.listReleasePolicies(projectId);
      return res.data;
    },
  });

  const environments = useQuery({
    queryKey: ["environments", projectId],
    queryFn: async () => {
      const res = await api.listEnvironments(projectId);
      return res.data;
    },
  });

  const models = useQuery({
    queryKey: ["models", projectId],
    queryFn: async () => {
      const res = await api.listModels(projectId);
      return res.data;
    },
  });

  // Mutations
  const createPolicyMutation = useMutation({
    mutationFn: async () => {
      const res = await api.createReleasePolicy(projectId, {
        name: policyName,
        min_reliability_score: parseFloat(minReliability) || undefined,
        max_regression_severity: maxRegSeverity,
        max_error_rate: parseFloat(maxErrorRate) || undefined,
        max_critical_alerts: parseInt(maxCritAlerts, 10) || 0,
        required_benchmark: reqBenchmark,
        required_evaluation: reqEvaluation,
        max_evidence_age_days: 14,
      });
      return res.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["release-policies", projectId] });
      setSelectedPolicy(data.id);
      setShowPolicyModal(false);
      setPolicyError(null);
    },
    onError: (err: any) => {
      setPolicyError(err.message || "Failed to create policy.");
    },
  });

  const createDecisionMutation = useMutation({
    mutationFn: async () => {
      const res = await api.createReleaseDecision(projectId, {
        environment_id: selectedEnv,
        model_id: selectedModel,
        release_policy_id: selectedPolicy,
      });
      return res.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["release-decisions", projectId] });
      setShowCreateModal(false);
      setCreateError(null);
      router.push(`/projects/${projectId}/decisions/${data.id}`);
    },
    onError: (err: any) => {
      setCreateError(err.message || "Failed to create decision.");
    },
  });

  const evaluateMutation = useMutation({
    mutationFn: async (decisionId: string) => {
      const res = await api.evaluateReleaseDecision(projectId, decisionId);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["release-decisions", projectId] });
    },
  });

  const decisionList = decisions.data ?? [];

  return (
    <AppShell>
      <div className="space-y-6" data-testid="release-decisions-view">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 mb-1">
              <Link href={`/projects/${projectId}`} className="hover:text-slate-900 transition">
                ← Back to Project
              </Link>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Release & Deployment Decisions (Go/No-Go Gate)
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Deterministic, explainable go/no-go deployment decisions backed by empirical test and regression evidence.
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            <Button variant="secondary" size="sm" onClick={() => setShowPolicyModal(true)} data-testid="create-policy-btn">
              + Create Policy
            </Button>
            <Button size="sm" onClick={() => setShowCreateModal(true)} data-testid="create-decision-btn">
              + New Decision
            </Button>
          </div>
        </div>

        {/* Decisions History Table */}
        <Card title={`Decision History (${decisionList.length})`} className="shadow-sm">
          {decisions.isLoading ? (
            <div className="p-8 text-center text-slate-400">Loading decisions…</div>
          ) : decisionList.length === 0 ? (
            <EmptyState
              title="No release decisions registered yet"
              description="Create a go/no-go release evaluation for a target model and environment."
              action={
                <Button onClick={() => setShowCreateModal(true)}>
                  + Create First Release Decision
                </Button>
              }
            />
          ) : (
            <Table>
              <TableHeader>
                <tr>
                  <TableHead>Status</TableHead>
                  <TableHead>Outcome Decision</TableHead>
                  <TableHead>Readiness Score</TableHead>
                  <TableHead>Target Model</TableHead>
                  <TableHead>Evaluated</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </tr>
              </TableHeader>
              <TableBody>
                {decisionList.map((d) => {
                  const outcomeVariant = d.outcome ? OUTCOME_VARIANTS[d.outcome] || "neutral" : null;
                  const modelObj = models.data?.find((m) => m.id === d.model_id);

                  return (
                    <TableRow key={d.id}>
                      <TableCell>
                        <StatusBadge status={d.status} />
                      </TableCell>
                      <TableCell>
                        {d.outcome && outcomeVariant ? (
                          <Badge variant={outcomeVariant} size="md" dot>
                            {d.outcome}
                          </Badge>
                        ) : (
                          <span className="text-xs text-slate-400">Not Evaluated</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {d.readiness_score !== null ? (
                          <span className="font-bold text-slate-900 font-mono text-sm">
                            {d.readiness_score} / 100
                          </span>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </TableCell>
                      <TableCell className="font-semibold text-slate-900">
                        {modelObj?.name || d.model_id.slice(0, 8)}
                      </TableCell>
                      <TableCell className="text-xs text-slate-500 font-mono">
                        {d.evaluated_at ? new Date(d.evaluated_at).toLocaleString() : "Never"}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Link href={`/projects/${projectId}/decisions/${d.id}`}>
                            <Button variant="secondary" size="sm" data-testid={`view-decision-${d.id}`}>
                              Details →
                            </Button>
                          </Link>
                          {d.status !== "DECIDED" && (
                            <Button
                              size="sm"
                              onClick={() => evaluateMutation.mutate(d.id)}
                              disabled={evaluateMutation.isPending}
                              isLoading={evaluateMutation.isPending}
                              data-testid={`evaluate-btn-${d.id}`}
                            >
                              Evaluate
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </Card>

        {/* Create Decision Modal */}
        <Modal
          isOpen={showCreateModal}
          onClose={() => setShowCreateModal(false)}
          title="Create Release Decision"
          description="Evaluate a model deployment against a predefined release policy"
        >
          {createError && <Alert kind="error" className="mb-4">{createError}</Alert>}

          <div className="space-y-4">
            <FormField label="Target Environment" htmlFor="cenv" required>
              <Select
                id="cenv"
                value={selectedEnv}
                onChange={(e) => setSelectedEnv(e.target.value)}
                data-testid="decision-env-select"
              >
                <option value="">Select an environment…</option>
                {environments.data?.map((env) => (
                  <option key={env.id} value={env.id}>
                    {env.name} ({env.environment_type})
                  </option>
                ))}
              </Select>
            </FormField>

            <FormField label="Target Model" htmlFor="cmodel" required>
              <Select
                id="cmodel"
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                data-testid="decision-model-select"
              >
                <option value="">Select a model…</option>
                {models.data?.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} ({m.model_identifier})
                  </option>
                ))}
              </Select>
            </FormField>

            <FormField label="Release Policy" htmlFor="cpolicy" required>
              <Select
                id="cpolicy"
                value={selectedPolicy}
                onChange={(e) => setSelectedPolicy(e.target.value)}
                data-testid="decision-policy-select"
              >
                <option value="">Select a release policy…</option>
                {policies.data?.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} (v{p.version})
                  </option>
                ))}
              </Select>
              {policies.data && policies.data.length === 0 && (
                <p className="text-xs text-amber-700 mt-1">
                  No policy exists yet. Click "Create Policy" first.
                </p>
              )}
            </FormField>

            <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
              <Button variant="secondary" onClick={() => setShowCreateModal(false)}>
                Cancel
              </Button>
              <Button
                onClick={() => createDecisionMutation.mutate()}
                disabled={!selectedEnv || !selectedModel || !selectedPolicy || createDecisionMutation.isPending}
                isLoading={createDecisionMutation.isPending}
                data-testid="create-decision-submit"
              >
                Create Decision
              </Button>
            </div>
          </div>
        </Modal>

        {/* Create Policy Modal */}
        <Modal
          isOpen={showPolicyModal}
          onClose={() => setShowPolicyModal(false)}
          title="Create Release Policy"
          description="Define deterministic go/no-go thresholds, regression boundaries, and error budgets"
        >
          {policyError && <Alert kind="error" className="mb-4">{policyError}</Alert>}

          <div className="space-y-4">
            <FormField label="Policy Name" htmlFor="polname" required>
              <Input
                id="polname"
                type="text"
                value={policyName}
                onChange={(e) => setPolicyName(e.target.value)}
                data-testid="policy-name-input"
              />
            </FormField>

            <div className="grid grid-cols-2 gap-4">
              <FormField label="Min Reliability Score (0–100)" htmlFor="polscore" required>
                <Input
                  id="polscore"
                  type="number"
                  value={minReliability}
                  onChange={(e) => setMinReliability(e.target.value)}
                  data-testid="policy-score-input"
                />
              </FormField>

              <FormField label="Max Regression Severity" htmlFor="polreg">
                <Select
                  id="polreg"
                  value={maxRegSeverity}
                  onChange={(e) => setMaxRegSeverity(e.target.value)}
                >
                  <option value="LOW">LOW</option>
                  <option value="MEDIUM">MEDIUM</option>
                  <option value="HIGH">HIGH</option>
                  <option value="CRITICAL">CRITICAL</option>
                </Select>
              </FormField>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <FormField label="Max Error Rate" htmlFor="polerr" hint="0.01 = 1% max errors">
                <Input
                  id="polerr"
                  type="number"
                  step="0.001"
                  value={maxErrorRate}
                  onChange={(e) => setMaxErrorRate(e.target.value)}
                />
              </FormField>

              <FormField label="Max Critical Alerts" htmlFor="polcrit">
                <Input
                  id="polcrit"
                  type="number"
                  value={maxCritAlerts}
                  onChange={(e) => setMaxCritAlerts(e.target.value)}
                />
              </FormField>
            </div>

            <div className="space-y-2 pt-2 border-t border-slate-100">
              <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer">
                <input
                  type="checkbox"
                  checked={reqBenchmark}
                  onChange={(e) => setReqBenchmark(e.target.checked)}
                  className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                />
                <span>Require completed benchmark suite run</span>
              </label>

              <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer">
                <input
                  type="checkbox"
                  checked={reqEvaluation}
                  onChange={(e) => setReqEvaluation(e.target.checked)}
                  className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                />
                <span>Require completed evaluation run</span>
              </label>
            </div>

            <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
              <Button variant="secondary" onClick={() => setShowPolicyModal(false)}>
                Cancel
              </Button>
              <Button
                onClick={() => createPolicyMutation.mutate()}
                disabled={!policyName || createPolicyMutation.isPending}
                isLoading={createPolicyMutation.isPending}
                data-testid="create-policy-submit"
              >
                Save Policy
              </Button>
            </div>
          </div>
        </Modal>
      </div>
    </AppShell>
  );
}
