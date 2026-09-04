"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FormField, Input, Select } from "@/components/ui/Input";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/Table";
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
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["models", projectId] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteModel(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["models", projectId] }),
  });

  const providerName = (id: string) =>
    providers.data?.data.find((p) => p.id === id)?.name ?? id;

  const canCreate = Boolean(name && modelIdentifier && providerId);
  const modelList = models.data?.data ?? [];

  return (
    <AppShell>
      <div className="space-y-6" data-testid="models-view">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 mb-1">
              <Link href={`/projects/${projectId}`} className="hover:text-slate-900 transition">
                ← Back to Project
              </Link>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              AI Models & Deployments
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Register LLMs and model endpoints to run evaluations, experiments, and production latency benchmarks.
            </p>
          </div>
        </div>

        {error ? <Alert kind="error">{error}</Alert> : null}

        {/* Add Model Form Card */}
        <Card title="Register AI Model" subtitle="Connect a model to a configured provider" className="shadow-sm">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <FormField label="Model Display Name" htmlFor="mname" required>
              <Input
                id="mname"
                aria-label="Model name"
                placeholder="e.g. GPT-4o Production"
                value={name}
                onChange={(e) => setName(e.target.value)}
                data-testid="model-name-input"
              />
            </FormField>

            <FormField label="Model Identifier" htmlFor="mid" required hint="e.g. gpt-4o, claude-3-5-sonnet">
              <Input
                id="mid"
                aria-label="Model identifier"
                placeholder="gpt-4o"
                value={modelIdentifier}
                onChange={(e) => setModelIdentifier(e.target.value)}
                data-testid="model-id-input"
              />
            </FormField>

            <FormField label="Provider" htmlFor="mprovider" required>
              <Select
                id="mprovider"
                aria-label="Provider"
                value={providerId}
                onChange={(e) => setProviderId(e.target.value)}
                data-testid="model-provider-select"
              >
                <option value="">Select a provider…</option>
                {providers.data?.data.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.provider_type})
                  </option>
                ))}
              </Select>
            </FormField>

            <FormField label="Environment" htmlFor="menv">
              <Select
                id="menv"
                aria-label="Environment"
                value={environmentId}
                onChange={(e) => setEnvironmentId(e.target.value)}
                data-testid="model-env-select"
              >
                <option value="">Select environment…</option>
                {environments.data?.data.map((env) => (
                  <option key={env.id} value={env.id}>
                    {env.name} ({env.environment_type})
                  </option>
                ))}
              </Select>
            </FormField>
          </div>

          <div className="mt-4 flex justify-end">
            <Button
              onClick={() => createMutation.mutate()}
              disabled={createMutation.isPending || !canCreate}
              isLoading={createMutation.isPending}
              data-testid="add-model-btn"
            >
              Add Model
            </Button>
          </div>
        </Card>

        {/* Model Catalog Table */}
        <Card title={`Configured Models (${modelList.length})`} className="shadow-sm">
          {models.isLoading ? (
            <div className="p-8 text-center text-slate-400">Loading models…</div>
          ) : modelList.length === 0 ? (
            <EmptyState
              title="No models registered yet"
              description="Register your first AI model above (requires at least one configured provider)."
            />
          ) : (
            <Table>
              <TableHeader>
                <tr>
                  <TableHead>Model Name</TableHead>
                  <TableHead>Model Identifier</TableHead>
                  <TableHead>Provider</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Latency & Health</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </tr>
              </TableHeader>
              <TableBody>
                {modelList.map((m) => (
                  <TableRow key={m.id}>
                    <TableCell className="font-semibold text-slate-900">{m.name}</TableCell>
                    <TableCell className="font-mono text-xs text-brand-700 bg-brand-50/50 px-2 py-0.5 rounded w-fit">
                      {m.model_identifier}
                    </TableCell>
                    <TableCell className="text-slate-600 font-medium">
                      {providerName(m.provider_id)}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={m.status} />
                    </TableCell>
                    <TableCell>
                      {m.last_health_status ? (
                        <div className="flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full bg-emerald-500" />
                          <span className="text-xs font-mono text-slate-600">
                            {m.last_latency_ms != null ? `${m.last_latency_ms}ms` : "OK"}
                          </span>
                        </div>
                      ) : (
                        <span className="text-xs text-slate-400">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant={consoleFor === m.id ? "primary" : "secondary"}
                          size="sm"
                          onClick={() => setConsoleFor(consoleFor === m.id ? null : m.id)}
                          data-testid={`invoke-model-${m.id}`}
                        >
                          {consoleFor === m.id ? "Hide Console" : "Invoke"}
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => testMutation.mutate(m.id)}
                          disabled={testMutation.isPending}
                        >
                          Test
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-rose-600 hover:bg-rose-50"
                          onClick={() => {
                            if (confirm(`Delete model ${m.name}?`)) deleteMutation.mutate(m.id);
                          }}
                        >
                          Delete
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Card>

        {/* Interactive Model Test Console */}
        {consoleFor ? (
          (() => {
            const model = modelList.find((m) => m.id === consoleFor);
            return model ? (
              <ModelTestConsole modelId={model.id} modelName={model.name} />
            ) : null;
          })()
        ) : null}
      </div>
    </AppShell>
  );
}
