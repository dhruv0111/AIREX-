"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

const SCOPES = [
  { value: "experiments:read", label: "Read Experiments" },
  { value: "experiments:write", label: "Write Experiments" },
  { value: "experiments:run", label: "Run Experiments & CI Runs" },
  { value: "datasets:read", label: "Read Datasets" },
  { value: "models:read", label: "Read Models" },
  { value: "quality_gates:read", label: "Read Quality Gates" },
];

export default function CISettingsPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const queryClient = useQueryClient();

  const [name, setName] = useState("");
  const [selectedScopes, setSelectedScopes] = useState<string[]>(["experiments:run"]);
  const [expiresInDays, setExpiresInDays] = useState<number | undefined>(undefined);
  
  const [newRawToken, setNewRawToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const tokens = useQuery({
    queryKey: ["service-tokens", projectId],
    queryFn: () => api.listServiceTokens(projectId),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.createServiceToken(projectId, {
        name,
        scopes: selectedScopes,
        expires_in_days: expiresInDays,
      }),
    onSuccess: (res) => {
      setName("");
      setExpiresInDays(undefined);
      setSelectedScopes(["experiments:run"]);
      setError(null);
      setNewRawToken(res.data.raw_token ?? null);
      queryClient.invalidateQueries({ queryKey: ["service-tokens", projectId] });
    },
    onError: (e) => setError(e instanceof ApiClientError ? e.message : "Failed to create service token"),
  });

  const revokeMutation = useMutation({
    mutationFn: (id: string) => api.revokeServiceToken(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["service-tokens", projectId] }),
  });

  const rotateMutation = useMutation({
    mutationFn: (id: string) => api.rotateServiceToken(id),
    onSuccess: (res) => {
      setError(null);
      setNewRawToken(res.data.raw_token ?? null);
      queryClient.invalidateQueries({ queryKey: ["service-tokens", projectId] });
    },
    onError: (e) => setError(e instanceof ApiClientError ? e.message : "Failed to rotate service token"),
  });

  const toggleScope = (scope: string) => {
    setSelectedScopes((prev) =>
      prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope]
    );
  };

  const ghSnippet = `name: AIREX CI Benchmarking
on: [push]
jobs:
  airex-eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install AIREX CLI
        run: pip install git+https://github.com/dhruv0111/AIREX-.git#egg=airex
      - name: Run AIREX Quality Gates
        env:
          AIREX_API_TOKEN: \$\{{ secrets.AIREX_API_TOKEN \}\}
          AIREX_PROJECT_ID: \$\{{ secrets.AIREX_PROJECT_ID \}\}
        run: python -m app.cli experiments run --config airex.yaml`;

  const glSnippet = `airex-eval:
  stage: test
  image: python:3.12
  script:
    - pip install git+https://github.com/dhruv0111/AIREX-.git#egg=airex
    - python -m app.cli experiments run --config airex.yaml
  variables:
    AIREX_API_TOKEN: $AIREX_API_TOKEN
    AIREX_PROJECT_ID: $AIREX_PROJECT_ID`;

  return (
    <AppShell>
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">CI/CD Integration Settings</h1>
          <p className="text-sm text-slate-500">Configure machine-to-machine API access tokens and integrate AIREX evaluation gates into your deployment pipelines.</p>
        </div>

        {error ? <Alert kind="error">{error}</Alert> : null}

        {newRawToken ? (
          <Alert kind="success">
            <div className="flex flex-col gap-2">
              <h3 className="font-bold text-green-950 text-sm">New API Token Generated</h3>
              <p className="font-semibold text-green-800 text-xs">
                Please copy your new API token now. You will not be able to see it again!
              </p>
              <div className="flex items-center gap-2 rounded border border-green-200 bg-green-50 p-3 font-mono text-sm break-all">
                <span className="flex-1">{newRawToken}</span>
                <Button
                  variant="ghost"
                  onClick={() => {
                    navigator.clipboard.writeText(newRawToken);
                  }}
                >
                  Copy
                </Button>
              </div>
              <Button variant="secondary" className="w-fit" onClick={() => setNewRawToken(null)}>
                Dismiss
              </Button>
            </div>
          </Alert>
        ) : null}

        <div className="grid gap-6 md:grid-cols-3">
          <div className="md:col-span-2 flex flex-col gap-6">
            <Card title="Active CI/CD Service Tokens">
              {tokens.isLoading ? (
                <p className="text-sm text-slate-400">Loading tokens…</p>
              ) : tokens.isError ? (
                <Alert kind="error">{(tokens.error as Error).message}</Alert>
              ) : !tokens.data?.data.length ? (
                <p className="text-sm text-slate-500">No active service tokens generated yet.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-slate-500">
                        <th className="py-2 pr-4">Name</th>
                        <th className="py-2 pr-4">Prefix</th>
                        <th className="py-2 pr-4">Scopes</th>
                        <th className="py-2 pr-4">Last Used</th>
                        <th className="py-2 pr-4">Expires</th>
                        <th className="py-2">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {tokens.data.data.map((tok) => (
                        <tr key={tok.id} className="border-b">
                          <td className="py-3 pr-4 font-semibold text-slate-900">{tok.name}</td>
                          <td className="py-3 pr-4 font-mono text-slate-500">{tok.token_prefix}</td>
                          <td className="py-3 pr-4">
                            <div className="flex flex-wrap gap-1">
                              {tok.scopes.map((s) => (
                                <span key={s} className="rounded bg-slate-100 px-1.5 py-0.5 text-xs font-mono text-slate-600">
                                  {s}
                                </span>
                              ))}
                            </div>
                          </td>
                          <td className="py-3 pr-4 text-slate-600">
                            {tok.last_used_at ? new Date(tok.last_used_at).toLocaleDateString() : "Never"}
                          </td>
                          <td className="py-3 pr-4 text-slate-600">
                            {tok.expires_at ? new Date(tok.expires_at).toLocaleDateString() : "Never"}
                          </td>
                          <td className="py-3">
                            <div className="flex gap-2">
                              <Button
                                variant="secondary"
                                className="px-2.5 py-1 text-xs"
                                onClick={() => rotateMutation.mutate(tok.id)}
                              >
                                Rotate
                              </Button>
                              <Button
                                variant="danger"
                                className="px-2.5 py-1 text-xs"
                                onClick={() => revokeMutation.mutate(tok.id)}
                              >
                                Revoke
                              </Button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>

            <Card title="CI/CD Configuration Snippets">
              <div className="flex flex-col gap-4">
                <div>
                  <h3 className="text-sm font-semibold text-slate-800">GitHub Actions Configuration</h3>
                  <p className="text-xs text-slate-500 mb-2">Add your token as secret `AIREX_API_TOKEN` and run evaluation gate step.</p>
                  <pre className="rounded-md bg-slate-900 p-3 text-xs font-mono text-slate-100 overflow-x-auto">
                    {ghSnippet}
                  </pre>
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-slate-800">GitLab CI/CD Configuration</h3>
                  <p className="text-xs text-slate-500 mb-2">Reference variable `$AIREX_API_TOKEN` under GitLab variables setup.</p>
                  <pre className="rounded-md bg-slate-900 p-3 text-xs font-mono text-slate-100 overflow-x-auto">
                    {glSnippet}
                  </pre>
                </div>
              </div>
            </Card>
          </div>

          <div>
            <Card title="Generate Service Token">
              <div className="flex flex-col gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">Token Name</label>
                  <input
                    aria-label="Token Name"
                    placeholder="e.g. GitHub Actions production gate"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">Expiration (Days)</label>
                  <input
                    aria-label="Expiration Days"
                    type="number"
                    placeholder="Never"
                    value={expiresInDays ?? ""}
                    onChange={(e) => setExpiresInDays(e.target.value ? parseInt(e.target.value) : undefined)}
                    className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">Scopes</label>
                  <div className="flex flex-col gap-2 mt-1">
                    {SCOPES.map((sc) => (
                      <label key={sc.value} className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={selectedScopes.includes(sc.value)}
                          onChange={() => toggleScope(sc.value)}
                          className="rounded border-slate-300"
                        />
                        {sc.label}
                      </label>
                    ))}
                  </div>
                </div>

                <Button
                  onClick={() => createMutation.mutate()}
                  disabled={createMutation.isPending || !name}
                  className="w-full"
                >
                  Generate Token
                </Button>
              </div>
            </Card>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
