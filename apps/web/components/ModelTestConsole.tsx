"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api, ApiClientError } from "@airex/api-client";
import type { ModelInvokeResponse } from "@airex/shared-types";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

interface ModelTestConsoleProps {
  modelId: string;
  modelName: string;
}

export function ModelTestConsole({ modelId, modelName }: ModelTestConsoleProps) {
  const [prompt, setPrompt] = useState("");
  const [temperature, setTemperature] = useState("0.7");
  const [maxTokens, setMaxTokens] = useState("256");
  const [result, setResult] = useState<ModelInvokeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const invoke = useMutation({
    mutationFn: () =>
      api.invokeModel(modelId, {
        messages: [{ role: "user", content: prompt }],
        temperature: Number(temperature),
        max_tokens: Number(maxTokens),
      }),
    onSuccess: (res) => {
      setResult(res.data);
      setError(null);
    },
    onError: (e) => setError(e instanceof ApiClientError ? e.message : "Invocation failed"),
  });

  return (
    <Card title={`Test console — ${modelName}`} className="mt-6">
      <div className="flex flex-col gap-3">
        <textarea
          aria-label="Prompt"
          placeholder="Enter a prompt to send to the model…"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={4}
          className="w-full rounded-md border border-slate-300 px-3 py-2"
        />
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-600">
            Temperature
            <input
              type="number"
              step="0.1"
              min="0"
              max="2"
              aria-label="Temperature"
              value={temperature}
              onChange={(e) => setTemperature(e.target.value)}
              className="w-20 rounded-md border border-slate-300 px-2 py-1"
            />
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            Max tokens
            <input
              type="number"
              min="1"
              aria-label="Max tokens"
              value={maxTokens}
              onChange={(e) => setMaxTokens(e.target.value)}
              className="w-24 rounded-md border border-slate-300 px-2 py-1"
            />
          </label>
          <Button
            onClick={() => invoke.mutate()}
            disabled={invoke.isPending || !prompt}
          >
            {invoke.isPending ? "Invoking…" : "Invoke"}
          </Button>
        </div>
      </div>

      {error ? <Alert kind="error" className="mt-4">{error}</Alert> : null}

      {result ? (
        <div className="mt-4 space-y-3">
          <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
            <p className="text-sm font-medium text-slate-500">Response</p>
            <pre className="mt-2 whitespace-pre-wrap font-mono text-sm text-slate-800">{result.content}</pre>
          </div>
          <div className="grid gap-3 text-sm sm:grid-cols-3">
            <div className="rounded-md border border-slate-200 p-3">
              <p className="text-slate-500">Latency</p>
              <p className="font-semibold text-slate-800">{result.latency_ms} ms</p>
            </div>
            <div className="rounded-md border border-slate-200 p-3">
              <p className="text-slate-500">Tokens</p>
              <p className="font-semibold text-slate-800">
                {result.usage.input_tokens} in / {result.usage.output_tokens} out
              </p>
            </div>
            <div className="rounded-md border border-slate-200 p-3">
              <p className="text-slate-500">Finish reason</p>
              <p className="font-semibold text-slate-800">{result.finish_reason}</p>
            </div>
          </div>
        </div>
      ) : null}
    </Card>
  );
}
