"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Alert } from "@/components/ui/Alert";
import { Card } from "@/components/ui/Card";

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const project = useQuery({
    queryKey: ["project", params.id],
    queryFn: () => api.getProject(params.id),
  });

  return (
    <AppShell>
      {project.isError ? (
        <Card>
          <Alert kind="error">{(project.error as Error).message}</Alert>
          <Link href="/projects" className="mt-4 inline-block text-sm text-brand hover:underline">
            ← Back to projects
          </Link>
        </Card>
      ) : project.isLoading ? (
        <Card>
          <p className="text-sm text-slate-400">Loading project…</p>
        </Card>
      ) : (
        <>
          <Link href="/projects" className="text-sm text-brand hover:underline">
            ← Back to projects
          </Link>
          <h1 className="mt-2 mb-4 text-2xl font-bold text-slate-900">
            {project.data?.data.name}
          </h1>
          <nav className="mb-6 flex flex-wrap gap-2 text-sm">
            <Link
              href={`/projects/${params.id}/providers`}
              className="rounded-md border border-slate-200 px-3 py-1.5 text-slate-600 hover:border-brand hover:text-brand"
            >
              Providers
            </Link>
            <Link
              href={`/projects/${params.id}/environments`}
              className="rounded-md border border-slate-200 px-3 py-1.5 text-slate-600 hover:border-brand hover:text-brand"
            >
              Environments
            </Link>
            <Link
              href={`/projects/${params.id}/models`}
              className="rounded-md border border-slate-200 px-3 py-1.5 text-slate-600 hover:border-brand hover:text-brand"
            >
              Models
            </Link>
            <Link
              href={`/projects/${params.id}/datasets`}
              className="rounded-md border border-slate-200 px-3 py-1.5 text-slate-600 hover:border-brand hover:text-brand"
            >
              Datasets
            </Link>
            <Link
              href={`/projects/${params.id}/evaluations`}
              className="rounded-md border border-slate-200 px-3 py-1.5 text-slate-600 hover:border-brand hover:text-brand"
            >
              Evaluations
            </Link>
            <Link
              href={`/projects/${params.id}/rubrics`}
              className="rounded-md border border-slate-200 px-3 py-1.5 text-slate-600 hover:border-brand hover:text-brand"
            >
              Rubrics
            </Link>
            <Link
              href={`/projects/${params.id}/generations`}
              className="rounded-md border border-slate-200 px-3 py-1.5 text-slate-600 hover:border-brand hover:text-brand"
            >
              Generations
            </Link>
          </nav>
          <div className="grid gap-6 md:grid-cols-2">
            <Card title="Details">
              <dl className="space-y-2 text-sm">
                <div>
                  <dt className="text-slate-500">Application type</dt>
                  <dd className="text-slate-800">{project.data?.data.application_type}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Environment / status</dt>
                  <dd className="text-slate-800">{project.data?.data.status}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Created</dt>
                  <dd className="text-slate-800">
                    {new Date(project.data?.data.created_at ?? "").toLocaleString()}
                  </dd>
                </div>
              </dl>
            </Card>
            <Card title="Description">
              <p className="text-sm text-slate-600">
                {project.data?.data.description ?? "No description."}
              </p>
            </Card>
          </div>
        </>
      )}
    </AppShell>
  );
}
