"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";

export default function ProjectsPage() {
  const projects = useQuery({ queryKey: ["projects"], queryFn: api.listProjects });

  return (
    <AppShell>
      <div className="space-y-6" data-testid="projects-view">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Projects & AI Workloads
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Manage your evaluated models, datasets, test suites, and deployment gates.
            </p>
          </div>
          <Link href="/projects/new">
            <Button data-testid="new-project-btn">+ Create Project</Button>
          </Link>
        </div>

        {projects.isError ? (
          <Alert kind="error">{(projects.error as Error).message}</Alert>
        ) : null}

        {projects.isLoading ? (
          <div className="p-8 text-center text-slate-400">Loading projects…</div>
        ) : projects.data && projects.data.data.length === 0 ? (
          <EmptyState
            title="No projects created yet"
            description="Create your first AI project to start running automated evaluations, benchmark comparisons, and go/no-go release gates."
            action={
              <Link href="/projects/new">
                <Button data-testid="create-first-project-btn">+ Create First Project</Button>
              </Link>
            }
          />
        ) : (
          <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
            {projects.data?.data.map((p) => (
              <Card
                key={p.id}
                className="hover:border-slate-300 hover:shadow-md transition-all flex flex-col justify-between"
              >
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono font-medium px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200">
                      {p.application_type || "generic_llm"}
                    </span>
                    <StatusBadge status={p.status} />
                  </div>
                  <div>
                    <Link
                      href={`/projects/${p.id}`}
                      className="text-base font-semibold text-slate-900 hover:text-brand-600 transition"
                      data-testid={`project-card-title-${p.id}`}
                    >
                      {p.name}
                    </Link>
                    <p className="mt-1 text-xs text-slate-500 line-clamp-2 leading-relaxed">
                      {p.description || "No description provided."}
                    </p>
                  </div>
                </div>

                <div className="pt-4 mt-4 border-t border-slate-100 flex items-center justify-between text-xs">
                  <span className="text-slate-400 font-mono">
                    {p.created_at ? new Date(p.created_at).toLocaleDateString() : "Active"}
                  </span>
                  <Link
                    href={`/projects/${p.id}`}
                    className="font-semibold text-brand-600 hover:text-brand-700"
                  >
                    Open Workspace →
                  </Link>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
