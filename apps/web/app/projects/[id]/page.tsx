"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Alert } from "@/components/ui/Alert";
import { Card, MetricCard } from "@/components/ui/Card";
import { StatusBadge, Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const project = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api.getProject(projectId),
  });

  const p = project.data?.data;

  return (
    <AppShell>
      <div className="space-y-8" data-testid="project-workspace">
        {project.isError ? (
          <Card>
            <Alert kind="error">{(project.error as Error).message}</Alert>
            <Link href="/projects" className="mt-4 inline-block text-sm font-semibold text-brand-600 hover:underline">
              ← Back to projects
            </Link>
          </Card>
        ) : project.isLoading ? (
          <div className="p-12 text-center text-slate-400">Loading project workspace…</div>
        ) : (
          <>
            {/* Header with Breadcrumb & Quick Actions */}
            <div className="border-b border-slate-200 pb-6">
              <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 mb-2">
                <Link href="/projects" className="hover:text-slate-900 transition">
                  Projects
                </Link>
                <span>/</span>
                <span className="text-slate-900">{p?.name}</span>
              </div>

              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div className="flex items-center gap-3">
                  <h1 className="text-2xl font-bold tracking-tight text-slate-900" data-testid="project-title">
                    {p?.name}
                  </h1>
                  <span className="font-mono text-xs font-medium px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200">
                    {p?.application_type}
                  </span>
                  <StatusBadge status={p?.status} />
                </div>

                <div className="flex items-center gap-3">
                  <Link href={`/projects/${projectId}/evaluations`}>
                    <Button size="sm" data-testid="quick-run-eval">
                      ▶ Run Evaluation
                    </Button>
                  </Link>
                  <Link href={`/projects/${projectId}/decisions`}>
                    <Button variant="secondary" size="sm" data-testid="quick-release-gate">
                      Go/No-Go Gate →
                    </Button>
                  </Link>
                </div>
              </div>

              {/* Sub-Navigation Bar */}
              <div className="mt-6 flex flex-wrap gap-1.5 border-t border-slate-100 pt-4 text-xs font-semibold">
                <Link
                  href={`/projects/${projectId}/models`}
                  className="rounded-lg px-3 py-1.5 text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition"
                  data-testid="tab-models"
                >
                  Models & Invoke
                </Link>
                <Link
                  href={`/projects/${projectId}/providers`}
                  className="rounded-lg px-3 py-1.5 text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition"
                  data-testid="tab-providers"
                >
                  Providers
                </Link>
                <Link
                  href={`/projects/${projectId}/datasets`}
                  className="rounded-lg px-3 py-1.5 text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition"
                  data-testid="tab-datasets"
                >
                  Datasets
                </Link>
                <Link
                  href={`/projects/${projectId}/rubrics`}
                  className="rounded-lg px-3 py-1.5 text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition"
                  data-testid="tab-rubrics"
                >
                  Rubrics
                </Link>
                <Link
                  href={`/projects/${projectId}/evaluations`}
                  className="rounded-lg px-3 py-1.5 text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition"
                  data-testid="tab-evaluations"
                >
                  Evaluations
                </Link>
                <Link
                  href={`/projects/${projectId}/experiments`}
                  className="rounded-lg px-3 py-1.5 text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition"
                  data-testid="tab-experiments"
                >
                  Experiments & A/B
                </Link>
                <Link
                  href={`/projects/${projectId}/agents`}
                  className="rounded-lg px-3 py-1.5 text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition"
                  data-testid="tab-agents"
                >
                  Agents & Tools
                </Link>
                <Link
                  href={`/projects/${projectId}/decisions`}
                  className="rounded-lg px-3 py-1.5 text-brand-700 bg-brand-50 border border-brand-200 hover:bg-brand-100 transition"
                  data-testid="tab-decisions"
                >
                  Release Decisions
                </Link>
                <Link
                  href={`/projects/${projectId}/observability`}
                  className="rounded-lg px-3 py-1.5 text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition"
                  data-testid="tab-observability"
                >
                  Observability & Traces
                </Link>
                <Link
                  href={`/projects/${projectId}/intelligence`}
                  className="rounded-lg px-3 py-1.5 text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition"
                  data-testid="tab-intelligence"
                >
                  Intelligence
                </Link>
              </div>
            </div>

            {/* Quick Metrics */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
              <MetricCard
                label="Application Framework"
                value={p?.application_type ?? "RAG Chatbot"}
                subvalue="Evaluation Pipeline"
                accent="brand"
              />
              <MetricCard
                label="Environment Status"
                value={p?.status ?? "ACTIVE"}
                subvalue="Zero regression gate active"
                accent="success"
              />
              <MetricCard
                label="Workspace Created"
                value={p?.created_at ? new Date(p.created_at).toLocaleDateString() : "Active"}
                subvalue="Automated audit tracking"
                accent="neutral"
              />
            </div>

            {/* Quick Launch Cards */}
            <div className="grid gap-6 md:grid-cols-2">
              <Card title="AI Evaluation & Testing Suites" subtitle="Run repeatable benchmark evaluations with custom rubrics">
                <div className="space-y-4">
                  <p className="text-sm text-slate-600 leading-relaxed">
                    Compare LLM outputs across immutable dataset versions. Run exact match, JSON schema, length, and LLM-as-a-judge scorers.
                  </p>
                  <div className="flex gap-3">
                    <Link href={`/projects/${projectId}/evaluations`}>
                      <Button size="sm">Launch Evaluation Suite →</Button>
                    </Link>
                    <Link href={`/projects/${projectId}/datasets`}>
                      <Button variant="secondary" size="sm">Manage Datasets</Button>
                    </Link>
                  </div>
                </div>
              </Card>

              <Card title="Release Quality Gate (Go/No-Go)" subtitle="Empirical validation before production deployment">
                <div className="space-y-4">
                  <p className="text-sm text-slate-600 leading-relaxed">
                    Evaluate candidate models against reliability policies, regression checks, error thresholds, and audit evidence.
                  </p>
                  <div className="flex gap-3">
                    <Link href={`/projects/${projectId}/decisions`}>
                      <Button size="sm">View Release Decisions →</Button>
                    </Link>
                    <Link href={`/projects/${projectId}/observability`}>
                      <Button variant="secondary" size="sm">Production Traces</Button>
                    </Link>
                  </div>
                </div>
              </Card>
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
}
