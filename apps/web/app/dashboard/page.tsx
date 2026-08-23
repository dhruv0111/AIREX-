"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

export default function DashboardPage() {
  const me = useQuery({ queryKey: ["me"], queryFn: api.me });
  const orgs = useQuery({ queryKey: ["organizations"], queryFn: api.listOrganizations });
  const projects = useQuery({ queryKey: ["projects"], queryFn: api.listProjects });

  if (me.isError) {
    return (
      <main className="flex min-h-screen items-center justify-center px-4">
        <Card title="Authentication required">
          <Alert kind="error">{(me.error as Error).message}</Alert>
          <p className="mt-4 text-sm text-slate-500">
            <Link href="/login" className="text-brand hover:underline">
              Sign in
            </Link>{" "}
            to continue.
          </p>
        </Card>
      </main>
    );
  }

  return (
    <AppShell>
      <h1 className="mb-6 text-2xl font-bold text-slate-900">Dashboard</h1>
      <div className="grid gap-6 md:grid-cols-3">
        <Card title="Organization">
          {orgs.isLoading ? (
            <p className="text-sm text-slate-400">Loading…</p>
          ) : orgs.data && orgs.data.data.length > 0 ? (
            <ul className="space-y-1 text-sm">
              {orgs.data.data.map((org) => (
                <li key={org.id} className="text-slate-700">
                  {org.name}
                  <Link
                    href={`/organizations/${org.id}/members`}
                    className="ml-2 text-xs font-medium text-brand hover:underline"
                  >
                    Members →
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-500">No organizations yet.</p>
          )}
        </Card>
        <Card title="Projects">
          {projects.isLoading ? (
            <p className="text-sm text-slate-400">Loading…</p>
          ) : projects.data && projects.data.data.length > 0 ? (
            <ul className="space-y-2 text-sm">
              {projects.data.data.map((p) => (
                <li key={p.id}>
                  <Link href={`/projects/${p.id}`} className="text-brand hover:underline">
                    {p.name}
                  </Link>
                  <span className="ml-2 rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
                    {p.status}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-500">No projects yet.</p>
          )}
          <div className="mt-4">
            <Link href="/projects/new">
              <Button>New project</Button>
            </Link>
          </div>
        </Card>
        <Card title="System status">
          <p className="text-sm text-slate-500">
            Signed in as <span className="font-medium text-slate-700">{me.data?.data.user.email}</span>
          </p>
          <p className="mt-2 text-xs text-slate-400">
            API: {process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}
          </p>
        </Card>
      </div>
    </AppShell>
  );
}
