"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, ApiClientError } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

const EXPERIMENT_TYPES = [
  "MODEL_COMPARISON",
  "PROMPT_COMPARISON",
  "DATASET_COMPARISON",
  "EVALUATOR_COMPARISON",
  "CONFIGURATION_COMPARISON",
];

const METRICS_OPTIONS = [
  "exact_match",
  "accuracy",
  "latency_ms",
  "estimated_cost",
  "combined_score",
  "judge_score",
];

const OPERATORS = ["GT", "GTE", "LT", "LTE", "EQ"];

export default function NewExperimentPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const router = useRouter();

  const [step, setStep] = useState(1);
  const [error, setError] = useState<string | null>(null);

  // Form State
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [type, setType] = useState("MODEL_COMPARISON");

  const [datasetId, setDatasetId] = useState("");
  const [datasetVersionId, setDatasetVersionId] = useState("");

  const [baselineModelId, setBaselineModelId] = useState("");
  const [baselinePromptContent, setBaselinePromptContent] = useState("");
  const [baselineConfig, setBaselineConfig] = useState("");

  const [candidateModelId, setCandidateModelId] = useState("");
  const [candidatePromptContent, setCandidatePromptContent] = useState("");
  const [candidateConfig, setCandidateConfig] = useState("");

  const [gates, setGates] = useState<Array<{
    metric_name: string;
    gate_type: string;
    operator: string;
    threshold: number;
    severity: string;
    is_required: boolean;
  }>>([]);

  const [newGateMetric, setNewGateMetric] = useState("exact_match");
  const [newGateType, setNewGateType] = useState("CANDIDATE_VALUE");
  const [newGateOp, setNewGateOp] = useState("GTE");
  const [newGateThreshold, setNewGateThreshold] = useState("0.90");
  const [newGateRequired, setNewGateRequired] = useState(true);

  // Queries
  const models = useQuery({
    queryKey: ["models", projectId],
    queryFn: () => api.listModels(projectId),
  });

  const datasets = useQuery({
    queryKey: ["datasets", projectId],
    queryFn: () => api.listDatasets(projectId, { page: 1, page_size: 50 }),
  });

  const versions = useQuery({
    queryKey: ["dataset-versions", datasetId],
    queryFn: () => api.listDatasetVersions(datasetId, { page: 1, page_size: 50 }),
    enabled: !!datasetId,
  });

  // Mutation
  const createMutation = useMutation({
    mutationFn: () => {
      const parsedBaselineConfig = baselineConfig ? JSON.parse(baselineConfig) : null;
      const parsedCandidateConfig = candidateConfig ? JSON.parse(candidateConfig) : null;

      return api.createExperiment(projectId, {
        project_id: projectId,
        name,
        description: description || null,
        experiment_type: type,
        dataset_version_id: datasetVersionId || null,
        model_id: baselineModelId || null,
        baseline: {
          model_id: baselineModelId || null,
          prompt_content: baselinePromptContent || null,
          dataset_version_id: datasetVersionId || null,
          configuration: parsedBaselineConfig,
        },
        candidate: {
          model_id: candidateModelId || null,
          prompt_content: candidatePromptContent || null,
          dataset_version_id: datasetVersionId || null,
          configuration: parsedCandidateConfig,
        },
        quality_gates: gates,
      });
    },
    onSuccess: (data) => {
      router.push(`/projects/${projectId}/experiments/${data.data.id}`);
    },
    onError: (err) => {
      setError(err instanceof ApiClientError ? err.message : "Failed to create experiment");
    },
  });

  const nextStep = () => setStep((s) => Math.min(s + 1, 6));
  const prevStep = () => setStep((s) => Math.max(s - 1, 1));

  const addGate = () => {
    setGates((g) => [
      ...g,
      {
        metric_name: newGateMetric,
        gate_type: newGateType,
        operator: newGateOp,
        threshold: Number(newGateThreshold) || 0,
        severity: "HIGH",
        is_required: newGateRequired,
      },
    ]);
  };

  const removeGate = (index: number) => {
    setGates((g) => g.filter((_, i) => i !== index));
  };

  return (
    <AppShell>
      <Link href={`/projects/${projectId}/experiments`} className="text-sm text-brand hover:underline">
        ← Experiments
      </Link>
      <h1 className="mt-2 mb-6 text-2xl font-bold text-slate-900">New Experiment Wizard</h1>

      {error && <Alert kind="error" className="mb-4">{error}</Alert>}

      {/* Step Indicator */}
      <div className="mb-8 flex justify-between border-b pb-4 text-xs font-semibold text-slate-400">
        <span className={step === 1 ? "text-brand" : ""}>1. Details</span>
        <span className={step === 2 ? "text-brand" : ""}>2. Dataset</span>
        <span className={step === 3 ? "text-brand" : ""}>3. Baseline Config</span>
        <span className={step === 4 ? "text-brand" : ""}>4. Candidate Config</span>
        <span className={step === 5 ? "text-brand" : ""}>5. Quality Gates</span>
        <span className={step === 6 ? "text-brand" : ""}>6. Review</span>
      </div>

      <Card>
        {step === 1 && (
          <div className="flex flex-col gap-4">
            <h2 className="text-lg font-semibold text-slate-900">Experiment details</h2>
            <label htmlFor="name-input" className="flex flex-col gap-1 text-sm text-slate-600">
              Name
              <input
                id="name-input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="GPT-4o Prompt v2 vs v3"
                className="rounded-md border border-slate-300 px-3 py-2 text-slate-900 focus:border-brand focus:outline-none"
              />
            </label>
            <label htmlFor="description-input" className="flex flex-col gap-1 text-sm text-slate-600">
              Description
              <textarea
                id="description-input"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional description of this experiment"
                className="rounded-md border border-slate-300 px-3 py-2 text-slate-900 focus:border-brand focus:outline-none"
              />
            </label>
            <label htmlFor="type-select" className="flex flex-col gap-1 text-sm text-slate-600">
              Experiment type
              <select
                id="type-select"
                value={type}
                onChange={(e) => setType(e.target.value)}
                className="rounded-md border border-slate-300 px-3 py-2 text-slate-900 focus:border-brand focus:outline-none"
              >
                {EXPERIMENT_TYPES.map((t) => (
                  <option key={t} value={t}>{t.replace("_", " ")}</option>
                ))}
              </select>
            </label>
          </div>
        )}

        {step === 2 && (
          <div className="flex flex-col gap-4">
            <h2 className="text-lg font-semibold text-slate-900">Select Dataset Version</h2>
            <label htmlFor="dataset-select" className="flex flex-col gap-1 text-sm text-slate-600">
              Dataset
              <select
                id="dataset-select"
                value={datasetId}
                onChange={(e) => {
                  setDatasetId(e.target.value);
                  setDatasetVersionId("");
                }}
                className="rounded-md border border-slate-300 px-3 py-2 text-slate-900 focus:border-brand focus:outline-none"
              >
                <option value="">Select a dataset…</option>
                {(datasets.data?.data ?? []).map((d) => (
                  <option key={d.id} value={d.id}>{d.name}</option>
                ))}
              </select>
            </label>
            {datasetId && (
              <label htmlFor="dataset-version-select" className="flex flex-col gap-1 text-sm text-slate-600">
                Dataset version
                <select
                  id="dataset-version-select"
                  value={datasetVersionId}
                  onChange={(e) => setDatasetVersionId(e.target.value)}
                  className="rounded-md border border-slate-300 px-3 py-2 text-slate-900 focus:border-brand focus:outline-none"
                >
                  <option value="">Select a version…</option>
                  {(versions.data?.data ?? []).map((v) => (
                    <option key={v.id} value={v.id}>
                      v{v.version_number} ({v.record_count} cases)
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
        )}

        {step === 3 && (
          <div className="flex flex-col gap-4">
            <h2 className="text-lg font-semibold text-slate-900">Baseline configuration</h2>
            <label htmlFor="baseline-model-select" className="flex flex-col gap-1 text-sm text-slate-600">
              Baseline model
              <select
                id="baseline-model-select"
                value={baselineModelId}
                onChange={(e) => setBaselineModelId(e.target.value)}
                className="rounded-md border border-slate-300 px-3 py-2 text-slate-900 focus:border-brand focus:outline-none"
              >
                <option value="">Select a model…</option>
                {(models.data?.data ?? []).map((m) => (
                  <option key={m.id} value={m.id}>{m.name} ({m.model_identifier})</option>
                ))}
              </select>
            </label>
            <label htmlFor="baseline-prompt-input" className="flex flex-col gap-1 text-sm text-slate-600">
              Prompt template (optional)
              <textarea
                id="baseline-prompt-input"
                value={baselinePromptContent}
                onChange={(e) => setBaselinePromptContent(e.target.value)}
                placeholder="E.g., You are a helpful assistant. Input: {{input}}"
                className="font-mono text-xs rounded-md border border-slate-300 px-3 py-2 text-slate-900 focus:border-brand focus:outline-none h-32"
              />
            </label>
            <label htmlFor="baseline-config-input" className="flex flex-col gap-1 text-sm text-slate-600">
              Extra variant configuration (JSON format)
              <textarea
                id="baseline-config-input"
                value={baselineConfig}
                onChange={(e) => setBaselineConfig(e.target.value)}
                placeholder='E.g., {"temperature": 0.2}'
                className="font-mono text-xs rounded-md border border-slate-300 px-3 py-2 text-slate-900 focus:border-brand focus:outline-none"
              />
            </label>
          </div>
        )}

        {step === 4 && (
          <div className="flex flex-col gap-4">
            <h2 className="text-lg font-semibold text-slate-900">Candidate configuration</h2>
            <label htmlFor="candidate-model-select" className="flex flex-col gap-1 text-sm text-slate-600">
              Candidate model
              <select
                id="candidate-model-select"
                value={candidateModelId}
                onChange={(e) => setCandidateModelId(e.target.value)}
                className="rounded-md border border-slate-300 px-3 py-2 text-slate-900 focus:border-brand focus:outline-none"
              >
                <option value="">Select a model…</option>
                {(models.data?.data ?? []).map((m) => (
                  <option key={m.id} value={m.id}>{m.name} ({m.model_identifier})</option>
                ))}
              </select>
            </label>
            <label htmlFor="candidate-prompt-input" className="flex flex-col gap-1 text-sm text-slate-600">
              Prompt template (optional)
              <textarea
                id="candidate-prompt-input"
                value={candidatePromptContent}
                onChange={(e) => setCandidatePromptContent(e.target.value)}
                placeholder="E.g., You are a strict JSON generator. Input: {{input}}"
                className="font-mono text-xs rounded-md border border-slate-300 px-3 py-2 text-slate-900 focus:border-brand focus:outline-none h-32"
              />
            </label>
            <label htmlFor="candidate-config-input" className="flex flex-col gap-1 text-sm text-slate-600">
              Extra variant configuration (JSON format)
              <textarea
                id="candidate-config-input"
                value={candidateConfig}
                onChange={(e) => setCandidateConfig(e.target.value)}
                placeholder='E.g., {"temperature": 0.7}'
                className="font-mono text-xs rounded-md border border-slate-300 px-3 py-2 text-slate-900 focus:border-brand focus:outline-none"
              />
            </label>
          </div>
        )}

        {step === 5 && (
          <div className="flex flex-col gap-4">
            <h2 className="text-lg font-semibold text-slate-900">Quality Gates Setup</h2>
            <div className="grid gap-3 md:grid-cols-3">
              <label className="flex flex-col gap-1 text-sm text-slate-600">
                Metric
                <select
                  value={newGateMetric}
                  onChange={(e) => setNewGateMetric(e.target.value)}
                  className="rounded-md border border-slate-300 px-3 py-2 text-slate-900 focus:border-brand focus:outline-none"
                >
                  {METRICS_OPTIONS.map((o) => (
                    <option key={o} value={o}>{o}</option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-sm text-slate-600">
                Gate type
                <select
                  value={newGateType}
                  onChange={(e) => setNewGateType(e.target.value)}
                  className="rounded-md border border-slate-300 px-3 py-2 text-slate-900 focus:border-brand focus:outline-none"
                >
                  <option value="CANDIDATE_VALUE">Candidate value</option>
                  <option value="RELATIVE_CHANGE">Relative change</option>
                  <option value="ABSOLUTE_CHANGE">Absolute change</option>
                </select>
              </label>
              <label className="flex flex-col gap-1 text-sm text-slate-600">
                Operator
                <select
                  value={newGateOp}
                  onChange={(e) => setNewGateOp(e.target.value)}
                  className="rounded-md border border-slate-300 px-3 py-2 text-slate-900 focus:border-brand focus:outline-none"
                >
                  {OPERATORS.map((op) => (
                    <option key={op} value={op}>{op}</option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-sm text-slate-600">
                Threshold
                <input
                  type="number"
                  step="0.01"
                  value={newGateThreshold}
                  onChange={(e) => setNewGateThreshold(e.target.value)}
                  className="rounded-md border border-slate-300 px-3 py-2 text-slate-900 focus:border-brand focus:outline-none"
                />
              </label>
              <label className="flex gap-2 items-center text-sm text-slate-600 mt-6">
                <input
                  type="checkbox"
                  checked={newGateRequired}
                  onChange={(e) => setNewGateRequired(e.target.checked)}
                  className="rounded border-slate-300 text-brand focus:ring-brand"
                />
                Required quality gate
              </label>
              <div className="mt-6 flex justify-end">
                <Button onClick={addGate}>Add Gate rule</Button>
              </div>
            </div>

            {/* List gates */}
            {gates.length > 0 && (
              <div className="mt-6">
                <h3 className="text-sm font-semibold text-slate-700 mb-2">Configured gate rules</h3>
                <ul className="divide-y text-sm">
                  {gates.map((g, i) => (
                    <li key={i} className="flex justify-between py-2 items-center">
                      <span>
                        {g.metric_name} ({g.gate_type}) {g.operator} {g.threshold}
                        {g.is_required ? (
                          <span className="ml-2 text-xs font-semibold text-red-600">Required</span>
                        ) : (
                          <span className="ml-2 text-xs font-semibold text-slate-400">Optional</span>
                        )}
                      </span>
                      <button onClick={() => removeGate(i)} className="text-xs text-red-500 hover:underline">
                        Remove
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {step === 6 && (
          <div className="flex flex-col gap-4">
            <h2 className="text-lg font-semibold text-slate-900">Review Experiment Configuration</h2>
            <dl className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt className="font-semibold text-slate-500">Name</dt>
                <dd className="text-slate-800 font-medium">{name}</dd>
              </div>
              <div>
                <dt className="font-semibold text-slate-500">Type</dt>
                <dd className="text-slate-800 font-medium">{type}</dd>
              </div>
              <div>
                <dt className="font-semibold text-slate-500">Dataset Version ID</dt>
                <dd className="text-slate-800 font-mono text-xs">{datasetVersionId || "None"}</dd>
              </div>
              <div>
                <dt className="font-semibold text-slate-500">Baseline Model ID</dt>
                <dd className="text-slate-800 font-mono text-xs">{baselineModelId || "Default"}</dd>
              </div>
              <div>
                <dt className="font-semibold text-slate-500">Candidate Model ID</dt>
                <dd className="text-slate-800 font-mono text-xs">{candidateModelId || "Default"}</dd>
              </div>
              <div>
                <dt className="font-semibold text-slate-500">Total Quality Gates</dt>
                <dd className="text-slate-800 font-medium">{gates.length}</dd>
              </div>
            </dl>
          </div>
        )}

        {/* Navigation Buttons */}
        <div className="mt-6 flex justify-between">
          {step > 1 ? (
            <Button variant="secondary" onClick={prevStep}>
              Back
            </Button>
          ) : (
            <div />
          )}

          {step < 6 ? (
            <Button onClick={nextStep} disabled={step === 1 && !name}>
              Continue
            </Button>
          ) : (
            <Button onClick={() => createMutation.mutate()} disabled={createMutation.isPending}>
              {createMutation.isPending ? "Creating…" : "Create Experiment"}
            </Button>
          )}
        </div>
      </Card>
    </AppShell>
  );
}
