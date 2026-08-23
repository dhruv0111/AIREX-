"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

const TYPES = ["LOCAL", "OPENAI", "ANTHROPIC", "GOOGLE"];

export default function ProvidersPage() {
  const params = useParams<{ id: string }>();
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
    // Refresh the providers list after a connection test so the updated
    // last_connection_status (e.g. CONNECTED) is fetched and rendered.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["providers"] }),
    onError: (e) => setError(e instanceof ApiClientError ? e.message : "Connection test failed"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteProvider(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["providers"] }),
  });

  return (
    <AppShell>
      <h1 className="mb-6 text-2xl font-bold text-slate-900">Providers</h1>
      {error ? <Alert kind="error">{error}</Alert> : null}

      <Card title="Add provider" className="mb-6">
        <div className="flex flex-col gap-3 md:flex-row">
          <input
            aria-label="Provider name"
            placeholder="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="flex-1 rounded-md border border-slate-300 px-3 py-2"
          />
          <select
            aria-label="Provider type"
            value={providerType}
            onChange={(e) => setProviderType(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2"
          >
            {TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          {providerType !== "LOCAL" ? (
            <input
              type="password"
              aria-label="API key"
              placeholder="API key"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="flex-1 rounded-md border border-slate-300 px-3 py-2"
            />
          ) : null}
          <Button onClick={() => createMutation.mutate()} disabled={createMutation.isPending || !name}>
            Add provider
          </Button>
        </div>
      </Card>

      {providers.isLoading ? (
        <Card><p className="text-sm text-slate-400">Loading providers…</p></Card>
      ) : providers.isError ? (
        <Card><Alert kind="error">{(providers.error as Error).message}</Alert></Card>
      ) : !providers.data?.data.length ? (
        <Card><p className="text-sm text-slate-500">No providers yet. Add one above.</p></Card>
      ) : (
        <Card>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-slate-500">
                <th className="py-2 pr-4">Name</th>
                <th className="py-2 pr-4">Type</th>
                <th className="py-2 pr-4">Key</th>
                <th className="py-2 pr-4">Status</th>
                <th className="py-2 pr-4">Connection</th>
                <th className="py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {providers.data.data.map((p) => (
                <tr key={p.id} className="border-b">
                  <td className="py-2 pr-4">{p.name}</td>
                  <td className="py-2 pr-4">{p.provider_type}</td>
                  <td className="py-2 pr-4 text-slate-400">{p.masked_key ?? "—"}</td>
                  <td className="py-2 pr-4">{p.status}</td>
                  <td className="py-2 pr-4">{testMutation.isPending ? "Testing…" : p.last_connection_status ?? "—"}</td>
                  <td className="py-2">
                    <div className="flex gap-2">
                      <Button variant="secondary" onClick={() => testMutation.mutate(p.id)}>
                        Test
                      </Button>
                      <Button
                        variant="danger"
                        onClick={() => {
                          if (confirm(`Delete provider ${p.name}?`)) deleteMutation.mutate(p.id);
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
    </AppShell>
  );
}
