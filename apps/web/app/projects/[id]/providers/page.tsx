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

const TYPES = ["LOCAL", "OPENAI", "ANTHROPIC", "GOOGLE"];

export default function ProvidersPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [providerType, setProviderType] = useState("LOCAL");
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState<string | null>(null);

  const providers = useQuery({ queryKey: ["providers"], queryFn: () => api.listProviders() });

  const createMutation = useMutation({
    mutationFn: () =>
      api.createProvider({ name, provider_type: providerType, api_key: apiKey || undefined }),
    onSuccess: () => {
      setName("");
      setApiKey("");
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["providers"] });
    },
    onError: (e) => setError(e instanceof ApiClientError ? e.message : "Failed to create provider"),
  });

  const testMutation = useMutation({
    mutationFn: (id: string) => api.testProvider(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["providers"] }),
    onError: (e) => setError(e instanceof ApiClientError ? e.message : "Connection test failed"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteProvider(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["providers"] }),
  });

  const providerList = providers.data?.data ?? [];

  return (
    <AppShell>
      <div className="space-y-6" data-testid="providers-view">
        {/* Navigation Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 mb-1">
              <Link href={`/projects/${projectId}`} className="hover:text-slate-900 transition">
                ← Back to Project
              </Link>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              AI Providers & API Connections
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Connect external AI model providers or local deterministic adapters. API keys are encrypted at rest with AES-256.
            </p>
          </div>
        </div>

        {error ? <Alert kind="error">{error}</Alert> : null}

        {/* Add Provider Card */}
        <Card title="Add AI Provider" subtitle="Configure a new LLM provider connection" className="shadow-sm">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <FormField label="Provider Name" htmlFor="pname" required>
              <Input
                id="pname"
                aria-label="Provider name"
                placeholder="e.g. Local E2E Adapter or OpenAI Prod"
                value={name}
                onChange={(e) => setName(e.target.value)}
                data-testid="provider-name-input"
              />
            </FormField>

            <FormField label="Provider Type" htmlFor="ptype" required>
              <Select
                id="ptype"
                aria-label="Provider type"
                value={providerType}
                onChange={(e) => setProviderType(e.target.value)}
                data-testid="provider-type-select"
              >
                {TYPES.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </Select>
            </FormField>

            {providerType !== "LOCAL" ? (
              <FormField label="API Key" htmlFor="pkey" required hint="Stored encrypted with Fernet AES">
                <Input
                  id="pkey"
                  type="password"
                  aria-label="API key"
                  placeholder="sk-••••••••••••••••"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  data-testid="provider-key-input"
                />
              </FormField>
            ) : (
              <div className="flex items-end pb-1.5 text-xs text-slate-500 font-medium">
                Local mock adapter (No API key required)
              </div>
            )}
          </div>

          <div className="mt-4 flex justify-end">
            <Button
              onClick={() => createMutation.mutate()}
              disabled={createMutation.isPending || !name}
              isLoading={createMutation.isPending}
              data-testid="add-provider-btn"
            >
              Add Provider
            </Button>
          </div>
        </Card>

        {/* Provider List Table */}
        <Card title={`Configured Providers (${providerList.length})`} className="shadow-sm">
          {providers.isLoading ? (
            <div className="p-8 text-center text-slate-400">Loading providers…</div>
          ) : providerList.length === 0 ? (
            <EmptyState
              title="No providers configured yet"
              description="Add a Local or Cloud provider above to begin connecting AI models."
            />
          ) : (
            <Table>
              <TableHeader>
                <tr>
                  <TableHead>Provider Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>API Key</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Connection Health</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </tr>
              </TableHeader>
              <TableBody>
                {providerList.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="font-semibold text-slate-900">{p.name}</TableCell>
                    <TableCell>
                      <Badge variant="neutral">{p.provider_type}</Badge>
                    </TableCell>
                    <TableCell className="font-mono text-xs text-slate-500">
                      {p.masked_key || (p.provider_type === "LOCAL" ? "— (Local)" : "sk-••••••••")}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={p.status} />
                    </TableCell>
                    <TableCell>
                      {p.last_connection_status === "CONNECTED" ? (
                        <Badge variant="success" dot>CONNECTED</Badge>
                      ) : p.last_connection_status ? (
                        <Badge variant="warning">{p.last_connection_status}</Badge>
                      ) : (
                        <span className="text-xs text-slate-400">Untested</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => testMutation.mutate(p.id)}
                          disabled={testMutation.isPending}
                          data-testid={`test-provider-${p.id}`}
                        >
                          {testMutation.isPending ? "Testing…" : "Test"}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-rose-600 hover:text-rose-700 hover:bg-rose-50"
                          onClick={() => {
                            if (confirm(`Delete provider ${p.name}?`)) deleteMutation.mutate(p.id);
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
      </div>
    </AppShell>
  );
}
