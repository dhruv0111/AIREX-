"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

export default function ProjectsPage() {
  const projects = useQuery({ queryKey: ["projects"], queryFn: api.listProjects });

  return (
    <AppShell>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Projects</h1>
        <Link href="/projects/new">
          <Button>New project</Button>
        </Link>
      </div>

      {projects.isError ? (
        <Alert kind="error">{(projects.error as Error).message}</Alert>
      ) : null}

      {projects.isLoading ? (
        <Card>
          <p className="text-sm text-slate-400">Loading projects…</p>
        </Card>
      ) : projects.data && projects.data.data.length === 0 ? (
        <Card>
          <p className="text-sm text-slate-500">No projects yet. Create your first project.</p>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {projects.data?.data.map((p) => (
            <Card key={p.id} title={p.name}>
              <p className="text-sm text-slate-500">{p.description ?? "No description"}</p>
              <div className="mt-3 flex items-center gap-3 text-xs text-slate-400">
                <span className="rounded bg-slate-100 px-2 py-0.5">{p.application_type}</span>
                <span className="rounded bg-slate-100 px-2 py-0.5">{p.status}</span>
              </div>
              <Link href={`/projects/${p.id}`} className="mt-4 inline-block text-sm font-medium text-brand hover:underline">
                View project →
              </Link>
            </Card>
          ))}
        </div>
      )}
    </AppShell>
  );
}
