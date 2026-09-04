"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api, ApiClientError } from "@airex/api-client";
import type { ModelInvokeResponse } from "@airex/shared-types";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FormField, Input, Textarea } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";

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
    <Card
      title={
        <div className="flex items-center gap-2">
          <span>Interactive Test Console</span>
          <Badge variant="brand">{modelName}</Badge>
        </div>
      }
      subtitle="Send ad-hoc test prompts to verify latency, token consumption, and model completion behavior."
      className="mt-6 border-brand-200 shadow-md"
      data-testid="model-test-console"
    >
      <div className="space-y-4">
        <FormField label="Prompt" htmlFor="prompt" required>
          <Textarea
            id="prompt"
            aria-label="Prompt"
            placeholder="Enter a prompt to send to the model (e.g. What are the key properties of reliable AI systems?)"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={3}
            data-testid="console-prompt-input"
          />
        </FormField>

        <div className="flex flex-wrap items-end gap-4">
          <FormField label="Temperature" htmlFor="temperature" className="w-32">
            <Input
              id="temperature"
              type="number"
              step="0.1"
              min="0"
              max="2"
              value={temperature}
              onChange={(e) => setTemperature(e.target.value)}
            />
          </FormField>

          <FormField label="Max Tokens" htmlFor="maxTokens" className="w-32">
            <Input
              id="maxTokens"
              type="number"
              min="1"
              value={maxTokens}
              onChange={(e) => setMaxTokens(e.target.value)}
            />
          </FormField>

          <Button
            onClick={() => invoke.mutate()}
            disabled={invoke.isPending || !prompt.trim()}
            isLoading={invoke.isPending}
            data-testid="console-invoke-btn"
          >
            Invoke Model
          </Button>
        </div>
      </div>

      {error ? <Alert kind="error" className="mt-4">{error}</Alert> : null}

      {result ? (
        <div className="mt-6 space-y-4 border-t border-slate-100 pt-5" data-testid="console-result">
          <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-4">
            <div className="flex items-center justify-between pb-2 border-b border-slate-200/60">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Model Output
              </span>
              <span className="text-xs font-mono text-emerald-600 font-semibold">
                ● 200 OK
              </span>
            </div>
            <pre className="mt-3 whitespace-pre-wrap font-sans text-sm text-slate-900 leading-relaxed">
              {result.content}
            </pre>
          </div>

          <div className="grid gap-3 text-sm sm:grid-cols-3">
            <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
              <p className="text-xs font-medium text-slate-500">Latency</p>
              <p className="text-lg font-bold text-brand-700 mt-0.5">{result.latency_ms} ms</p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
              <p className="text-xs font-medium text-slate-500">Tokens</p>
              <p className="text-lg font-bold text-slate-900 mt-0.5">
                {result.usage.input_tokens} in / {result.usage.output_tokens} out
              </p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
              <p className="text-xs font-medium text-slate-500">Finish reason</p>
              <p className="text-lg font-bold text-slate-900 mt-0.5">{result.finish_reason}</p>
            </div>
          </div>
        </div>
      ) : null}
    </Card>
  );
}
