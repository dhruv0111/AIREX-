"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, MetricCard } from "@/components/ui/Card";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { MetricSkeleton } from "@/components/ui/LoadingSkeleton";

export default function DashboardPage() {
  const me = useQuery({ queryKey: ["me"], queryFn: api.me });
  const orgs = useQuery({ queryKey: ["organizations"], queryFn: api.listOrganizations });
  const projects = useQuery({ queryKey: ["projects"], queryFn: api.listProjects });
  const readiness = useQuery({ queryKey: ["system-readiness"], queryFn: api.getSystemReadiness });

  if (me.isError) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
        <Card title="Authentication Required" className="max-w-md w-full">
          <Alert kind="error">{(me.error as Error).message}</Alert>
          <div className="mt-6 flex justify-end">
            <Link href="/login">
              <Button>Sign in to continue</Button>
            </Link>
          </div>
        </Card>
      </main>
    );
  }

  const projectList = projects.data?.data ?? [];
  const orgList = orgs.data?.data ?? [];
  const primaryOrg = orgList[0];

  return (
    <AppShell>
      <div className="space-y-8" data-testid="dashboard-view">
        {/* Dashboard Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-6">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight text-slate-900" data-testid="dashboard-heading">
                Reliability Command Center
              </h1>
              {primaryOrg && (
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-brand-50 text-brand-700 border border-brand-200">
                  {primaryOrg.name}
                </span>
              )}
            </div>
            <p className="mt-1 text-sm text-slate-500">
              Deterministic AI evaluations, regression safeguards, and production observability.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Link href="/admin/operations">
              <Button variant="secondary" size="sm" data-testid="goto-operations">
                SRE Telemetry →
              </Button>
            </Link>
            <Link href="/projects/new">
              <Button size="sm" data-testid="create-project-btn">
                + Create Project
              </Button>
            </Link>
          </div>
        </div>

        {/* Executive KPI Metrics */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5" data-testid="kpi-metrics-grid">
          {projects.isLoading ? (
            <>
              <MetricSkeleton />
              <MetricSkeleton />
              <MetricSkeleton />
              <MetricSkeleton />
            </>
          ) : (
            <>
              <MetricCard
                label="Active Projects"
                value={projectList.length}
                subvalue="Active AI pipelines"
                accent="brand"
                testId="metric-projects"
                badge={<Badge variant="brand">{projectList.length} Active</Badge>}
              />
              <MetricCard
                label="System Health"
                value={(readiness.data as any)?.overall_status ?? (readiness.data as any)?.data?.overall_status ?? "HEALTHY"}
                subvalue="Subsystems operational"
                accent="success"
                testId="metric-health"
                badge={<Badge variant="success" dot>100% SLA</Badge>}
              />
              <MetricCard
                label="Evaluations & Gate"
                value="Active"
                subvalue="Deterministic scoring"
                accent="brand"
                testId="metric-evals"
                badge={<Badge variant="info">Ready</Badge>}
              />
              <MetricCard
                label="Release Policy"
                value="Enforced"
                subvalue="Go/No-Go verification"
                accent="success"
                testId="metric-release"
                badge={<Badge variant="success">Protected</Badge>}
              />
            </>
          )}
        </div>

        {/* Main Content Grid: Projects & Workspace Details */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Projects Column (2/3 width) */}
          <div className="lg:col-span-2 space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-900 tracking-tight">
                AI Projects & Workloads
              </h2>
              <Link
                href="/projects"
                className="text-xs font-semibold text-brand-600 hover:text-brand-700 hover:underline"
              >
                View all ({projectList.length}) →
              </Link>
            </div>

            {projects.isLoading ? (
              <div className="p-8 text-center text-slate-400">Loading projects…</div>
            ) : projectList.length === 0 ? (
              <EmptyState
                title="No projects configured yet"
                description="Create your first AI project to configure models, upload test datasets, and run automated reliability evaluations."
                action={
                  <Link href="/projects/new">
                    <Button data-testid="empty-create-project-btn">+ Create First Project</Button>
                  </Link>
                }
              />
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="project-cards-grid">
                {projectList.map((p) => (
                  <Card
                    key={p.id}
                    className="hover:border-slate-300 hover:shadow-md transition-all group flex flex-col justify-between"
                  >
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-mono font-medium px-2 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
                          {p.application_type || "general_llm"}
                        </span>
                        <StatusBadge status={p.status} />
                      </div>
                      <div>
                        <Link
                          href={`/projects/${p.id}`}
                          className="text-base font-semibold text-slate-900 group-hover:text-brand-600 transition"
                          data-testid={`project-link-${p.id}`}
                        >
                          {p.name}
                        </Link>
                        <p className="mt-1 text-xs text-slate-500 line-clamp-2 leading-relaxed">
                          {p.description || "Production AI workload under active reliability monitoring."}
                        </p>
                      </div>
                    </div>

                    <div className="pt-4 mt-4 border-t border-slate-100 flex items-center justify-between text-xs">
                      <span className="text-slate-400">
                        {p.created_at ? new Date(p.created_at).toLocaleDateString() : "Active"}
                      </span>
                      <Link
                        href={`/projects/${p.id}`}
                        className="font-semibold text-brand-600 hover:text-brand-700 flex items-center gap-1"
                      >
                        Open Workspace →
                      </Link>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>

          {/* Sidebar Column: Organization, Quick Links & System Status */}
          <div className="space-y-6">
            <Card title="Workspace & Organization">
              {orgs.isLoading ? (
                <p className="text-xs text-slate-400">Loading…</p>
              ) : orgList.length > 0 ? (
                <div className="space-y-3 text-sm">
                  {orgList.map((org) => (
                    <div
                      key={org.id}
                      className="p-3 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-between"
                    >
                      <div>
                        <div className="font-semibold text-slate-900">{org.name}</div>
                        <div className="text-xs text-slate-500 font-mono">slug: {org.slug}</div>
                      </div>
                      <Link
                        href={`/organizations/${org.id}/members`}
                        className="text-xs font-semibold text-brand-600 hover:underline"
                      >
                        Members →
                      </Link>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-500">No organizations found.</p>
              )}
            </Card>

            <Card title="Platform Modules">
              <div className="space-y-2 text-sm">
                <Link
                  href="/admin/operations"
                  className="flex items-center justify-between p-2.5 rounded-lg border border-slate-100 hover:bg-slate-50 hover:border-slate-200 transition"
                >
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-500" />
                    <span className="font-medium text-slate-800">Production SRE & Ops</span>
                  </div>
                  <span className="text-xs text-slate-400">Live</span>
                </Link>

                <Link
                  href="/admin/compliance"
                  className="flex items-center justify-between p-2.5 rounded-lg border border-slate-100 hover:bg-slate-50 hover:border-slate-200 transition"
                >
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-brand-500" />
                    <span className="font-medium text-slate-800">Compliance & Audit</span>
                  </div>
                  <span className="text-xs text-slate-400">SOC 2 / ISO</span>
                </Link>

                <Link
                  href="/admin/system"
                  className="flex items-center justify-between p-2.5 rounded-lg border border-slate-100 hover:bg-slate-50 hover:border-slate-200 transition"
                >
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-slate-400" />
                    <span className="font-medium text-slate-800">System Diagnostics</span>
                  </div>
                  <span className="text-xs text-slate-400">Health</span>
                </Link>
              </div>
            </Card>

            <Card title="Signed-in Operator">
              <div className="text-sm space-y-2">
                <div className="flex justify-between py-1 border-b border-slate-100">
                  <span className="text-slate-500">Account:</span>
                  <span className="font-medium text-slate-900">{me.data?.data.user.email}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-100">
                  <span className="text-slate-500">Role:</span>
                  <Badge variant="brand">ADMIN</Badge>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-slate-500">API Endpoint:</span>
                  <span className="text-xs font-mono text-slate-600">
                    {process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}
                  </span>
                </div>
              </div>
            </Card>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
