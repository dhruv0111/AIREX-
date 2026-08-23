"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

const ENV_TYPES = ["DEVELOPMENT", "STAGING", "PRODUCTION"];

export default function EnvironmentsPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [envType, setEnvType] = useState("DEVELOPMENT");
  const [error, setError] = useState<string | null>(null);

  const environments = useQuery({
    queryKey: ["environments", projectId],
    queryFn: () => api.listEnvironments(projectId),
  });

  const createMutation = useMutation({
    mutationFn: () => api.createEnvironment(projectId, { name, environment_type: envType }),
    onSuccess: () => {
      setName("");
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["environments", projectId] });
    },
    onError: (e) => setError(e instanceof ApiClientError ? e.message : "Failed to create environment"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteEnvironment(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["environments", projectId] }),
  });

  return (
    <AppShell>
      <h1 className="mb-6 text-2xl font-bold text-slate-900">Environments</h1>
      {error ? <Alert kind="error">{error}</Alert> : null}

      <Card title="Add environment" className="mb-6">
        <div className="flex flex-col gap-3 md:flex-row">
          <input
            aria-label="Environment name"
            placeholder="Name (e.g. Production)"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="flex-1 rounded-md border border-slate-300 px-3 py-2"
          />
          <select
            aria-label="Environment type"
            value={envType}
            onChange={(e) => setEnvType(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2"
          >
            {ENV_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          <Button onClick={() => createMutation.mutate()} disabled={createMutation.isPending || !name}>
            Add environment
          </Button>
        </div>
      </Card>

      {environments.isLoading ? (
        <Card><p className="text-sm text-slate-400">Loading environments…</p></Card>
      ) : environments.isError ? (
        <Card><Alert kind="error">{(environments.error as Error).message}</Alert></Card>
      ) : !environments.data?.data.length ? (
        <Card><p className="text-sm text-slate-500">No environments yet. Add one above (one per type).</p></Card>
      ) : (
        <Card>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-slate-500">
                <th className="py-2 pr-4">Name</th>
                <th className="py-2 pr-4">Type</th>
                <th className="py-2 pr-4">Status</th>
                <th className="py-2 pr-4">Default model</th>
                <th className="py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {environments.data.data.map((env) => (
                <tr key={env.id} className="border-b">
                  <td className="py-2 pr-4">{env.name}</td>
                  <td className="py-2 pr-4">{env.environment_type}</td>
                  <td className="py-2 pr-4">{env.status}</td>
                  <td className="py-2 pr-4 text-slate-400">{env.default_model_id ?? "—"}</td>
                  <td className="py-2">
                    <Button
                      variant="danger"
                      onClick={() => {
                        if (confirm(`Delete environment ${env.name}?`)) deleteMutation.mutate(env.id);
                      }}
                    >
                      Delete
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </AppShell>
  );
}
