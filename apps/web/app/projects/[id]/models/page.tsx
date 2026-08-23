"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ModelTestConsole } from "@/components/ModelTestConsole";

export default function ModelsPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [modelIdentifier, setModelIdentifier] = useState("");
  const [providerId, setProviderId] = useState("");
  const [environmentId, setEnvironmentId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [consoleFor, setConsoleFor] = useState<string | null>(null);

  const models = useQuery({
    queryKey: ["models", projectId],
    queryFn: () => api.listModels(projectId),
  });

  const providers = useQuery({
    queryKey: ["providers"],
    queryFn: () => api.listProviders(),
  });

  const environments = useQuery({
    queryKey: ["environments", projectId],
    queryFn: () => api.listEnvironments(projectId),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.createModel(projectId, {
        name,
        model_identifier: modelIdentifier,
        provider_id: providerId,
        environment_id: environmentId || undefined,
      }),
    onSuccess: () => {
      setName("");
      setModelIdentifier("");
      setProviderId("");
      setEnvironmentId("");
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["models", projectId] });
    },
    onError: (e) => setError(e instanceof ApiClientError ? e.message : "Failed to create model"),
  });

  const testMutation = useMutation({
    mutationFn: (id: string) => api.testModel(id),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteModel(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["models", projectId] }),
  });

  const providerName = (id: string) =>
    providers.data?.data.find((p) => p.id === id)?.name ?? id;

  const canCreate = Boolean(name && modelIdentifier && providerId);

  return (
    <AppShell>
      <h1 className="mb-6 text-2xl font-bold text-slate-900">Models</h1>
      {error ? <Alert kind="error">{error}</Alert> : null}

      <Card title="Add model" className="mb-6">
        <div className="flex flex-col gap-3 md:flex-row">
          <input
            aria-label="Model name"
            placeholder="Name (e.g. gpt-4o)"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="flex-1 rounded-md border border-slate-300 px-3 py-2"
          />
          <input
            aria-label="Model identifier"
            placeholder="Model id (e.g. gpt-4o)"
            value={modelIdentifier}
            onChange={(e) => setModelIdentifier(e.target.value)}
            className="flex-1 rounded-md border border-slate-300 px-3 py-2"
          />
          <select
            aria-label="Provider"
            value={providerId}
            onChange={(e) => setProviderId(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2"
          >
            <option value="">Provider…</option>
            {providers.data?.data.map((p) => (
              <option key={p.id} value={p.id}>{p.name} ({p.provider_type})</option>
            ))}
          </select>
          <select
            aria-label="Environment"
            value={environmentId}
            onChange={(e) => setEnvironmentId(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2"
          >
            <option value="">Environment…</option>
            {environments.data?.data.map((env) => (
              <option key={env.id} value={env.id}>{env.name} ({env.environment_type})</option>
            ))}
          </select>
          <Button onClick={() => createMutation.mutate()} disabled={createMutation.isPending || !canCreate}>
            Add model
          </Button>
        </div>
      </Card>

      {models.isLoading ? (
        <Card><p className="text-sm text-slate-400">Loading models…</p></Card>
      ) : models.isError ? (
        <Card><Alert kind="error">{(models.error as Error).message}</Alert></Card>
      ) : !models.data?.data.length ? (
        <Card><p className="text-sm text-slate-500">No models yet. Add one above (requires at least one provider).</p></Card>
      ) : (
        <Card>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-slate-500">
                <th className="py-2 pr-4">Name</th>
                <th className="py-2 pr-4">Model id</th>
                <th className="py-2 pr-4">Provider</th>
                <th className="py-2 pr-4">Status</th>
                <th className="py-2 pr-4">Health</th>
                <th className="py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {models.data.data.map((m) => (
                <tr key={m.id} className="border-b">
                  <td className="py-2 pr-4">{m.name}</td>
                  <td className="py-2 pr-4 font-mono text-xs">{m.model_identifier}</td>
                  <td className="py-2 pr-4">{providerName(m.provider_id)}</td>
                  <td className="py-2 pr-4">{m.status}</td>
                  <td className="py-2 pr-4">
                    {m.last_health_status ?? "—"}
                    {m.last_latency_ms != null ? ` (${m.last_latency_ms}ms)` : ""}
                  </td>
                  <td className="py-2">
                    <div className="flex flex-wrap gap-2">
                      <Button variant="secondary" onClick={() => setConsoleFor(consoleFor === m.id ? null : m.id)}>
                        {consoleFor === m.id ? "Hide console" : "Invoke"}
                      </Button>
                      <Button variant="secondary" onClick={() => testMutation.mutate(m.id)}>
                        Test
                      </Button>
                      <Button
                        variant="danger"
                        onClick={() => {
                          if (confirm(`Delete model ${m.name}?`)) deleteMutation.mutate(m.id);
                        }}
                      >
                        Delete
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {consoleFor ? (
        (() => {
          const model = models.data?.data.find((m) => m.id === consoleFor);
          return model ? <ModelTestConsole modelId={model.id} modelName={model.name} /> : null;
        })()
      ) : null}
    </AppShell>
  );
}
